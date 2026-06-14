from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_serenity_method_radar as serenity_radar
from config import get_deepseek_auto_explain_enabled, get_deepseek_factor_explain_mode
from storage.sqlite_meta import SQLiteMetaStore

from . import model_strategy_service, packet_service, storage_service, tushare_task_service
from .task_service import create_task_record, create_task_stub, update_task_status

SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
DEEPSEEK_FACTOR_PROMPT_VERSION = "factor_deepseek_explanation_prompt.v1"
FACTOR_UNIVERSE_RESEARCH_PLAN_MODES = {"watchlist", "custom_pool", "full_pool"}
FACTOR_UNIVERSE_RESEARCH_PLAN_DATASETS = ("factor_values", "daily", "daily_basic", "moneyflow", "trade_cal")
FACTOR_UNIVERSE_ITEM_SECRET_MARKERS = ("token", "api_key", "secret", "password", "authorization", "bearer")
FACTOR_UNIVERSE_WORKER_BATCH_SYMBOL_LIMIT = 500
FACTOR_UNIVERSE_WORKER_BATCH_MIN_SYMBOLS = 20
FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES = (
    "storage_read_plan",
    "worker_batch_scope",
    "cross_sectional_rank",
    "zscore",
    "neutralization",
    "factor_combination",
    "result_summary",
    "promotion_review",
)
FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES = (
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
FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASE_LABELS = {
    "scope_ticket_review": "Scope ticket review",
    "explicit_worker_task_creation": "Explicit worker task creation",
    "worker_runtime_binding": "Worker runtime binding",
    "storage_read_execution": "Storage read execution",
    "cross_sectional_rank_execution": "Cross-sectional rank execution",
    "zscore_execution": "Z-score execution",
    "neutralization_execution": "Neutralization execution",
    "factor_combination_execution": "Factor combination execution",
    "result_summary_persistence": "Result summary persistence",
    "production_promotion_review": "Production promotion review",
}
FACTOR_TEST_PROVIDER_SMALL_POOL_SYMBOL_LIMIT = 20
FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS = 5
FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS = 60
FACTOR_TEST_PROVIDER_SMALL_POOL_ALLOWED_DATASETS = ("factor_values", "daily", "daily_basic", "moneyflow", "trade_cal")
FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS = (
    "ic",
    "rank_ic",
    "icir",
    "group_return",
    "top_bottom",
    "max_drawdown",
    "neutral_ic",
    "out_of_sample_decay",
    "cost_model",
)
FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES = (
    "scope_ticket_review",
    "explicit_provider_task_creation",
    "provider_call_ledger_capture",
    "sample_row_collection",
    "multi_horizon_forward_returns",
    "rolling_ic_icir_validation",
    "cost_turnover_validation",
    "neutralization_stability_validation",
    "pit_bias_controls_validation",
    "promotion_review",
)
FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASE_LABELS = {
    "scope_ticket_review": "Scope ticket review",
    "explicit_provider_task_creation": "Explicit provider task creation",
    "provider_call_ledger_capture": "Provider call ledger capture",
    "sample_row_collection": "Sample row collection",
    "multi_horizon_forward_returns": "Multi-horizon forward returns",
    "rolling_ic_icir_validation": "Rolling IC / ICIR validation",
    "cost_turnover_validation": "Cost and turnover validation",
    "neutralization_stability_validation": "Neutralization stability validation",
    "pit_bias_controls_validation": "PIT/lookahead/survivorship validation",
    "promotion_review": "Promotion review",
}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _local_ledger_boundary() -> dict[str, Any]:
    return {
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def read_factor_quant_cache() -> dict[str, Any]:
    packet = dict(packet_service.build_factor_quant_cache())
    now = _now_iso()
    if packet.get("mode") == "cache_only":
        packet["cache_mode"] = "cache_only"
        packet["mode"] = "light"
    packet["cache_only"] = True
    packet["read_only"] = True
    packet["external_calls_triggered"] = False
    packet["tushare_called"] = False
    packet["deepseek_called"] = False
    packet["github_called"] = False
    packet["does_not_execute_trades"] = True
    packet["does_not_modify_strategy_action"] = True
    packet["deepseek_explain_governance"] = _deepseek_explain_governance()
    packet["score_chart_payload"] = _factor_score_chart_payload(packet)
    packet, universe_rank_ledger = _attach_factor_universe_local_rank_zscore_dry_run(packet, now)
    packet = _attach_factor_universe_execution_readiness(packet)
    packet, universe_execution_receipt_ledger = _attach_factor_universe_execution_readiness_receipt(packet, now)
    packet, universe_activation_receipt_ledger = _attach_factor_universe_execution_activation_receipt(packet, now)
    packet, universe_batch_recipe_ledger = _attach_factor_universe_worker_batch_execution_recipe(packet, now)
    packet = _attach_deepseek_json_stability_audit(packet, governance=packet["deepseek_explain_governance"])
    packet, deepseek_activation_ledger = _attach_deepseek_production_activation_receipt(packet, now)
    packet, deepseek_benchmark_recipe_ledger = _attach_deepseek_provider_benchmark_execution_recipe(packet, now)
    packet, storage_query_ledger = _attach_factor_test_storage_query_consumption(packet, now)
    packet, local_dataset_ledger = _attach_factor_test_local_dataset_sample_evidence(packet, now)
    packet, production_validation_ledger = _attach_factor_test_production_validation_qa_contract(packet, now)
    packet, provider_validation_blocker_ledger = _attach_factor_test_provider_validation_blocker_audit(packet, now)
    packet, provider_sample_readiness_ledger = _attach_factor_test_provider_sample_readiness_receipt(packet, now)
    packet, provider_sample_activation_ledger = _attach_factor_test_provider_sample_activation_receipt(packet, now)
    packet, provider_small_pool_recipe_ledger = _attach_factor_test_provider_small_pool_execution_recipe(packet, now)
    cache_ledger = _factor_quant_cache_call_ledger(packet, now)
    existing_ledger = packet.get("call_ledger") if isinstance(packet.get("call_ledger"), list) else []
    packet["cache_call_ledger"] = cache_ledger
    packet["call_ledger"] = (
        cache_ledger
        + universe_rank_ledger
        + universe_execution_receipt_ledger
        + universe_activation_receipt_ledger
        + universe_batch_recipe_ledger
        + deepseek_activation_ledger
        + deepseek_benchmark_recipe_ledger
        + storage_query_ledger
        + local_dataset_ledger
        + production_validation_ledger
        + provider_validation_blocker_ledger
        + provider_sample_readiness_ledger
        + provider_sample_activation_ledger
        + provider_small_pool_recipe_ledger
        + list(existing_ledger)
    )
    cache_warning = "GET /api/factor-quant/cache 只读取本地多因子图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
    universe_rank_warning = "Factor Universe rank/zscore dry-run 只读本地 factor_values 样本；样本不足时保持 blocked，不代表 full-pool 生产研究完成。"
    universe_execution_receipt_warning = "Factor Universe execution readiness receipt 只说明下一步显式 worker batch 是否可进入；不会运行 full-pool、rank/zscore、中性化或 provider 验收。"
    universe_activation_receipt_warning = "Factor Universe execution activation receipt 只把下一步固定为显式 worker batch 生产验收；不会创建任务、启动 worker、计算 full-pool/rank/zscore/neutralization 或 provider 验收。"
    universe_batch_recipe_warning = "Factor Universe worker-batch execution recipe 只固定未来显式 worker 批量研究验收顺序；不会创建任务、启动 worker、计算 rank/zscore/neutralization 或 provider 验收。"
    deepseek_activation_warning = "DeepSeek production activation receipt 只汇总下一步生产解释验收缺口；不会调用模型，不代表 provider benchmark、response_format 强约束或 auto_after_task 生产完成。"
    deepseek_benchmark_recipe_warning = "DeepSeek provider benchmark execution recipe 只固定未来显式 benchmark 的样本、ledger、retry、成本和 promotion 标准；不会调用 DeepSeek 或完成生产解释。"
    storage_query_warning = "Factor Test Lab 只消费本地 factor_values DuckDB 查询合同；不把查询样本当作生产 IC 验收或交易信号。"
    local_dataset_warning = "Factor Test Lab 本地 Parquet 样本证据只做样本充分性审计；不足以证明真实小股票池或生产级因子验证。"
    provider_blocker_warning = "Factor Test provider validation blocker audit 只汇总真实小股票池/全市场验收缺口；不会调用 provider、不会计算交易信号。"
    provider_sample_receipt_warning = "Factor Test provider small-pool readiness receipt 只说明下一步显式 POST 验收是否可执行；不会调用 provider 或提升生产验收。"
    provider_sample_activation_warning = "Factor Test provider small-pool activation receipt 只串联下一步真实小股票池验收清单；不会调用 provider、创建任务或标记生产完成。"
    provider_small_pool_recipe_warning = "Factor Test provider small-pool execution recipe 只固定未来真实小股票池验收顺序；不会调用 Tushare、计算生产 IC 或标记生产完成。"
    existing_warnings = packet.get("warnings") if isinstance(packet.get("warnings"), list) else []
    owned_warnings = {
        cache_warning,
        universe_rank_warning,
        universe_execution_receipt_warning,
        universe_activation_receipt_warning,
        universe_batch_recipe_warning,
        deepseek_activation_warning,
        deepseek_benchmark_recipe_warning,
        storage_query_warning,
        local_dataset_warning,
        provider_blocker_warning,
        provider_sample_receipt_warning,
        provider_sample_activation_warning,
        provider_small_pool_recipe_warning,
    }
    packet["warnings"] = [
        cache_warning,
        universe_rank_warning,
        universe_execution_receipt_warning,
        universe_activation_receipt_warning,
        deepseek_activation_warning,
        deepseek_benchmark_recipe_warning,
        storage_query_warning,
        local_dataset_warning,
        provider_blocker_warning,
        provider_sample_receipt_warning,
        provider_sample_activation_warning,
    ] + [
        item
        for item in existing_warnings
        if item not in owned_warnings
    ]
    return packet


def _factor_universe_local_rank_zscore_dry_run(now: str) -> dict[str, Any]:
    sample_limit = 1000
    factor_packet = storage_service.factor_values_status(limit=sample_limit)
    factor_rows = _storage_query_rows(factor_packet)
    usable_rows = [
        row
        for row in factor_rows
        if str(row.get("ts_code") or "").strip()
        and str(row.get("trade_date") or "").strip()
        and str(row.get("factor_key") or "").strip()
        and _is_finite_number(row.get("raw_value"))
        and str(row.get("data_status") or "").lower() not in {"missing", "expired", "stale", "historical", "unknown"}
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in usable_rows:
        groups.setdefault((str(row.get("trade_date")), str(row.get("factor_key"))), []).append(row)
    eligible_groups = {
        key: rows
        for key, rows in groups.items()
        if len({str(row.get("ts_code")) for row in rows}) >= 5
    }
    preview_rows: list[dict[str, Any]] = []
    for (trade_date, factor_key), rows in sorted(eligible_groups.items())[:3]:
        values = [float(row.get("raw_value")) for row in rows]
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        std_value = math.sqrt(variance)
        sorted_rows = sorted(rows, key=lambda item: float(item.get("raw_value")))
        denominator = max(len(sorted_rows) - 1, 1)
        for index, row in enumerate(sorted_rows[:5]):
            raw_value = float(row.get("raw_value"))
            preview_rows.append(
                {
                    "trade_date": trade_date,
                    "factor_key": factor_key,
                    "ts_code": str(row.get("ts_code")),
                    "rank_pct_preview": round(index / denominator, 6),
                    "zscore_preview": round((raw_value - mean_value) / std_value, 6) if std_value else 0.0,
                    "research_only_preview": True,
                    "enters_strategy_action": False,
                }
            )
    dry_run_executed = bool(eligible_groups)
    unique_tickers = {str(row.get("ts_code")) for row in usable_rows}
    unique_dates = {str(row.get("trade_date")) for row in usable_rows}
    unique_factors = {str(row.get("factor_key")) for row in usable_rows}

    def _row(criterion: str, status: str, evidence: str, next_action: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "blocks_full_pool_research": status != "passed",
            "evidence": evidence,
            "next_action": next_action,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "factor_values_local_sample_present",
            "passed" if factor_packet.get("status") == "ready" and factor_rows else "blocked",
            f"factor_values_status={factor_packet.get('status')}; returned_rows={len(factor_rows)}",
            "Populate factor_values through approved local task/cache paths before rank/zscore dry-run.",
        ),
        _row(
            "usable_cross_section_present",
            "passed" if eligible_groups else "blocked",
            f"eligible_trade_date_factor_groups={len(eligible_groups)}; usable_rows={len(usable_rows)}; unique_tickers={len(unique_tickers)}",
            "Need at least five usable tickers per trade_date/factor_key group before local rank/zscore dry-run can execute.",
        ),
        _row(
            "sample_window_visible",
            "passed" if unique_dates and unique_factors else "blocked",
            f"unique_trade_dates={len(unique_dates)}; factor_keys={len(unique_factors)}",
            "Keep trade-date and factor-key coverage visible before promoting any universe research step.",
        ),
        _row(
            "production_flags_stay_false",
            "passed",
            "cross_sectional_rank_zscore_done=false; full_pool_validation_done=false; production_factor_universe_complete=false",
            "Only a future worker-backed/provider-backed validation may promote production universe flags.",
        ),
        _row(
            "frontend_does_not_compute_rank_zscore",
            "passed",
            "React displays this dry-run contract only; rank/zscore preview, if present, is built server-side from local cache rows.",
            "Keep rank/zscore out of page render and frontend action calculation paths.",
        ),
        _row(
            "trade_action_isolation",
            "passed",
            "Local rank/zscore dry-run does not execute trades, mutate strategy action, or enter next-session projection.",
            "Preserve universe research outputs as research-only evidence until a separately approved trading design exists.",
        ),
        _row(
            "external_call_boundary",
            "passed",
            "Dry-run reads local factor_values storage cache only and does not call Tushare, DeepSeek, or GitHub.",
            "Keep provider-backed universe validation behind explicit future POST task gates.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_full_pool_research"]]
    status = "local_rank_zscore_dry_run_ready_research_only" if dry_run_executed else "local_rank_zscore_dry_run_blocked_not_enough_data"
    return {
        "schema_version": "factor_universe_local_rank_zscore_dry_run.v1",
        "status": status,
        "scope": "local_factor_values_rank_zscore_dry_run_not_full_pool_validation",
        "created_at": now,
        "dataset": "factor_values",
        "sample_limit": sample_limit,
        "storage_status": factor_packet.get("status") or "missing",
        "returned_row_count": len(factor_rows),
        "usable_row_count": len(usable_rows),
        "unique_ticker_count": len(unique_tickers),
        "unique_trade_date_count": len(unique_dates),
        "factor_key_count": len(unique_factors),
        "eligible_group_count": len(eligible_groups),
        "rank_zscore_dry_run_executed": dry_run_executed,
        "rank_zscore_preview_rows": preview_rows,
        "rank_zscore_preview_row_count": len(preview_rows),
        "metrics_are_research_only": True,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "production_factor_universe_complete": False,
        "page_render_starts_full_pool": False,
        "frontend_computes_rank_zscore": False,
        "partial_pool_is_full_market_proof": False,
        "cache_only": True,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "auto_refresh_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "criterion_count": len(rows),
        "blocking_criterion_count": len(blocking_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocking_rows],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_universe_rank_zscore_dry_run",
                "request_params_safe": {
                    "dataset": "factor_values",
                    "sample_limit": sample_limit,
                    "scope": "local_factor_values_rank_zscore_dry_run_not_full_pool_validation",
                    "rank_zscore_dry_run_executed": dry_run_executed,
                    "production_factor_universe_complete": False,
                },
                "row_count": len(usable_rows),
                "data_date": max(unique_dates) if unique_dates else None,
                "local_fetched_at": now,
                "call_status": status,
                "error_message_safe": str(factor_packet.get("error_message_safe") or "")[:240],
                **_local_ledger_boundary(),
            }
        ],
        "note": "This dry-run is local/research-only. It may preview rank/zscore only when a usable local cross-section exists, and it never marks full-pool or production universe validation complete.",
    }


def _attach_factor_universe_local_rank_zscore_dry_run(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dry_run = _factor_universe_local_rank_zscore_dry_run(now)
    packet["universe_local_rank_zscore_dry_run"] = dry_run
    packet["universe_local_rank_zscore_rows"] = list(dry_run.get("rows") or [])
    packet["universe_local_rank_zscore_preview_rows"] = list(dry_run.get("rank_zscore_preview_rows") or [])
    contract = packet.get("universe_research_contract") if isinstance(packet.get("universe_research_contract"), dict) else {}
    if contract:
        contract = dict(contract)
        contract["local_rank_zscore_dry_run_status"] = dry_run["status"]
        contract["local_rank_zscore_dry_run_executed"] = dry_run["rank_zscore_dry_run_executed"]
        contract["local_rank_zscore_preview_row_count"] = dry_run["rank_zscore_preview_row_count"]
        contract["cross_sectional_rank_zscore_done"] = False
        contract["full_sample_neutralization_done"] = False
        contract["full_pool_validation_done"] = False
        contract["production_factor_universe_complete"] = False
        contract["frontend_computes_rank_zscore"] = False
        packet["universe_research_contract"] = contract
    return packet, list(dry_run.get("call_ledger") or [])


def _attach_factor_universe_execution_readiness(packet: dict[str, Any]) -> dict[str, Any]:
    audit = factor_research.build_factor_universe_execution_readiness_audit(
        contract=packet.get("universe_research_contract"),
        mode_rows=packet.get("universe_research_mode_rows"),
        task_plan=packet.get("universe_research_task_plan"),
    )
    packet["universe_execution_readiness_audit"] = audit
    packet["universe_execution_readiness_rows"] = list(audit.get("rows") or [])
    contract = packet.get("universe_research_contract") if isinstance(packet.get("universe_research_contract"), dict) else {}
    if contract:
        contract = dict(contract)
        contract["execution_readiness_status"] = audit.get("status")
        contract["production_factor_universe_complete"] = audit.get("production_factor_universe_complete")
        contract["production_blocker_count"] = audit.get("production_blocker_count")
        packet["universe_research_contract"] = contract
    return packet


def _factor_universe_execution_readiness_receipt_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    *,
    required_before_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_promotion": bool(required_before_promotion),
        "evidence": evidence,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
    }


def _factor_universe_execution_readiness_receipt(packet: dict[str, Any], now: str) -> dict[str, Any]:
    audit = packet.get("universe_execution_readiness_audit") if isinstance(packet.get("universe_execution_readiness_audit"), dict) else {}
    task_plan = packet.get("universe_research_task_plan") if isinstance(packet.get("universe_research_task_plan"), dict) else {}
    rank_zscore = packet.get("universe_local_rank_zscore_dry_run") if isinstance(packet.get("universe_local_rank_zscore_dry_run"), dict) else {}
    contract = packet.get("universe_research_contract") if isinstance(packet.get("universe_research_contract"), dict) else {}

    read_plan_ready = bool(audit.get("read_plan_ready") and task_plan.get("status") == "read_plan_ready")
    storage_contract_consumed = bool(audit.get("storage_query_contract_consumed") and task_plan.get("storage_query_contract_count"))
    worker_plan_ready = bool(audit.get("worker_task_consumption_plan_ready") or task_plan.get("worker_task_consumption_plan_ready"))
    local_rank_preview_ready = bool(rank_zscore.get("rank_zscore_dry_run_executed"))
    frontend_safe = bool(
        audit.get("page_render_starts_full_pool") is False
        and audit.get("frontend_computes_rank_zscore") is False
        and audit.get("partial_pool_is_full_market_proof") is False
    )
    trade_safe = bool(
        audit.get("does_not_execute_trades") is True
        and audit.get("does_not_modify_strategy_action") is True
        and contract.get("does_not_execute_trades", True) is True
    )
    local_contracts_safe = bool(
        audit.get("schema_version") == "factor_universe_execution_readiness_audit.v1"
        and rank_zscore.get("schema_version") == "factor_universe_local_rank_zscore_dry_run.v1"
        and audit.get("external_calls_triggered") is False
        and rank_zscore.get("external_calls_triggered") is False
        and audit.get("production_factor_universe_complete") is False
        and rank_zscore.get("production_factor_universe_complete") is False
    )
    large_universe_done = bool(audit.get("large_universe_pipeline_done"))
    full_pool_done = bool(audit.get("full_pool_validation_done"))
    rank_done = bool(audit.get("cross_sectional_rank_zscore_done"))
    neutralization_done = bool(audit.get("neutralization_done"))
    production_blockers = [
        str(row.get("criterion"))
        for row in packet.get("universe_execution_readiness_rows", [])
        if isinstance(row, dict) and row.get("production_blocker")
    ]
    missing_evidence_items = sorted(
        {
            *production_blockers,
            *[str(item) for item in rank_zscore.get("blocking_criteria", []) if item],
        }
    )
    ready_for_explicit_worker_batch_task = bool(
        read_plan_ready
        and storage_contract_consumed
        and worker_plan_ready
        and frontend_safe
        and trade_safe
        and local_contracts_safe
        and not large_universe_done
    )
    rows = [
        _factor_universe_execution_readiness_receipt_row(
            "button_gated_worker_batch_boundary",
            "passed_static_policy",
            True,
            "Large-universe research may only move forward through an explicit POST worker/task step; GET cache and render stay read-only.",
            required_before_promotion=False,
        ),
        _factor_universe_execution_readiness_receipt_row(
            "read_plan_ready",
            "passed_read_plan_ready" if read_plan_ready else "blocked_read_plan_missing",
            read_plan_ready,
            f"task_plan_status={task_plan.get('status')}; requested_universe_mode={task_plan.get('requested_universe_mode') or audit.get('requested_universe_mode')}",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "storage_contract_consumed",
            "passed_storage_contracts" if storage_contract_consumed else "blocked_storage_contracts",
            storage_contract_consumed,
            f"storage_query_contract_count={task_plan.get('storage_query_contract_count')}; dataset_count={task_plan.get('dataset_count')}",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "worker_task_plan_ready",
            "passed_worker_plan_ready" if worker_plan_ready else "blocked_worker_plan_missing",
            worker_plan_ready,
            f"worker_task_consumption_plan_ready={worker_plan_ready}; large_universe_pipeline_done={large_universe_done}",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "local_rank_zscore_preview_boundary",
            "passed_preview_available" if local_rank_preview_ready else "blocked_or_pending_local_cross_section",
            local_rank_preview_ready,
            f"rank_zscore_status={rank_zscore.get('status')}; eligible_groups={rank_zscore.get('eligible_group_count')}; preview_rows={rank_zscore.get('rank_zscore_preview_row_count')}",
            required_before_promotion=False,
        ),
        _factor_universe_execution_readiness_receipt_row(
            "local_contracts_are_no_batch_or_provider_call",
            "passed_no_provider_call" if local_contracts_safe else "blocked_external_boundary",
            local_contracts_safe,
            "Execution readiness and local rank/zscore dry-run are local/read-only contracts and cannot call providers, models, or GitHub.",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "frontend_and_partial_pool_boundary",
            "passed_frontend_read_only" if frontend_safe else "blocked_frontend_or_partial_pool",
            frontend_safe,
            f"page_render_starts_full_pool={audit.get('page_render_starts_full_pool')}; frontend_computes_rank_zscore={audit.get('frontend_computes_rank_zscore')}; partial_pool_is_full_market_proof={audit.get('partial_pool_is_full_market_proof')}",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "production_research_blockers_visible",
            "passed_blockers_visible" if production_blockers else "blocked_blocker_audit_missing",
            bool(production_blockers),
            f"production_blocker_count={audit.get('production_blocker_count')}; blockers={production_blockers}",
            required_before_promotion=False,
        ),
        _factor_universe_execution_readiness_receipt_row(
            "production_completion_evidence_ticket",
            "ready_for_promotion_review" if full_pool_done and rank_done and neutralization_done else "pending_worker_rank_neutralization_full_pool_evidence",
            full_pool_done and rank_done and neutralization_done,
            f"large_universe_pipeline_done={large_universe_done}; rank_zscore_done={rank_done}; neutralization_done={neutralization_done}; full_pool_validation_done={full_pool_done}",
        ),
        _factor_universe_execution_readiness_receipt_row(
            "trade_and_action_boundary",
            "passed",
            trade_safe,
            "Receipt never executes trades, mutates strategy action, enters evidence effects, or modifies next-session projection.",
            required_before_promotion=False,
        ),
    ]
    blocked_rows = [row["criterion"] for row in rows if row["required_before_promotion"] and not row["passed"]]
    allowed_next_step = (
        "review_prior_factor_universe_full_pool_evidence"
        if full_pool_done and rank_done and neutralization_done
        else "explicit_post_task_factor_universe_worker_batch_research"
        if ready_for_explicit_worker_batch_task
        else "generate_button_gated_universe_research_read_plan"
    )
    return {
        "schema_version": "factor_universe_execution_readiness_receipt.v1",
        "status": "universe_execution_receipt_ready_for_promotion_review"
        if full_pool_done and rank_done and neutralization_done
        else "universe_execution_receipt_ready_worker_batch_pending"
        if ready_for_explicit_worker_batch_task
        else "universe_execution_receipt_blocked_read_plan_or_contract",
        "scope": "local_factor_universe_execution_readiness_receipt_no_batch_or_provider_execution",
        "created_at": now,
        "ltg": "LTG-04/LTG-11",
        "local_receipt_ready": True,
        "ready_for_explicit_worker_batch_task": ready_for_explicit_worker_batch_task,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache full-pool execution",
            "React render full-pool execution",
            "frontend rank/zscore calculation",
            "partial pool as full-market proof",
            "read-plan as production completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "read_plan_ready": read_plan_ready,
        "storage_query_contract_consumed": storage_contract_consumed,
        "worker_task_consumption_plan_ready": worker_plan_ready,
        "local_rank_zscore_dry_run_executed": local_rank_preview_ready,
        "large_universe_pipeline_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "full_pool_validation_done": False,
        "production_factor_universe_complete": False,
        "production_blocker_count": int(audit.get("production_blocker_count") or len(production_blockers)),
        "production_blockers": production_blockers,
        "provider_refresh_called_by_receipt": False,
        "worker_batch_executed_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "row_count": len(rows),
        "blocked_readiness_count": len(blocked_rows),
        "blocked_readiness_items": blocked_rows,
        "missing_evidence_items": missing_evidence_items,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_universe_execution_readiness_receipt",
                "request_params_safe": {
                    "scope": "local_factor_universe_execution_readiness_receipt_no_batch_or_provider_execution",
                    "requested_universe_mode": audit.get("requested_universe_mode"),
                    "ready_for_explicit_worker_batch_task": ready_for_explicit_worker_batch_task,
                    "production_factor_universe_complete": False,
                },
                "row_count": len(rows),
                "data_date": rank_zscore.get("call_ledger", [{}])[0].get("data_date") if isinstance(rank_zscore.get("call_ledger"), list) and rank_zscore.get("call_ledger") else None,
                "local_fetched_at": now,
                "call_status": allowed_next_step,
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This receipt summarizes the next safe LTG-04 universe execution step. It never runs worker batch research, rank/zscore production metrics, neutralization, provider validation, or trades.",
    }


def _attach_factor_universe_execution_readiness_receipt(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _factor_universe_execution_readiness_receipt(packet, now)
    packet["universe_execution_readiness_receipt"] = receipt
    packet["universe_execution_readiness_receipt_rows"] = list(receipt.get("rows") or [])
    contract = packet.get("universe_research_contract") if isinstance(packet.get("universe_research_contract"), dict) else {}
    if contract:
        contract = dict(contract)
        contract["universe_execution_readiness_receipt_ready"] = True
        contract["ready_for_explicit_worker_batch_task"] = bool(receipt.get("ready_for_explicit_worker_batch_task"))
        contract["production_factor_universe_complete"] = False
        contract["full_pool_validation_done"] = False
        packet["universe_research_contract"] = contract
    return packet, list(receipt.get("call_ledger") or [])


def _factor_universe_execution_activation_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    *,
    blocks_production_completion: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_production_completion": bool(blocks_production_completion),
        "evidence": evidence,
        "cache_get_external_calls": False,
        "activation_receipt_external_calls_triggered": False,
        "worker_batch_created_by_receipt": False,
        "worker_batch_executed_by_receipt": False,
        "provider_refresh_called_by_receipt": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
    }


def _factor_universe_execution_activation_receipt(packet: dict[str, Any], now: str) -> dict[str, Any]:
    readiness = packet.get("universe_execution_readiness_audit") if isinstance(packet.get("universe_execution_readiness_audit"), dict) else {}
    readiness_receipt = packet.get("universe_execution_readiness_receipt") if isinstance(packet.get("universe_execution_readiness_receipt"), dict) else {}
    rank_zscore = packet.get("universe_local_rank_zscore_dry_run") if isinstance(packet.get("universe_local_rank_zscore_dry_run"), dict) else {}
    task_plan = packet.get("universe_research_task_plan") if isinstance(packet.get("universe_research_task_plan"), dict) else {}

    ready_for_worker_batch = bool(readiness_receipt.get("ready_for_explicit_worker_batch_task"))
    read_plan_ready = bool(readiness.get("read_plan_ready") and task_plan.get("status") == "read_plan_ready")
    storage_ready = bool(readiness.get("storage_query_contract_consumed"))
    worker_plan_ready = bool(readiness.get("worker_task_consumption_plan_ready"))
    frontend_safe = bool(
        readiness.get("page_render_starts_full_pool") is False
        and readiness.get("frontend_computes_rank_zscore") is False
        and readiness.get("partial_pool_is_full_market_proof") is False
    )
    trade_safe = bool(
        readiness.get("does_not_execute_trades") is True
        and readiness.get("does_not_modify_strategy_action") is True
        and readiness_receipt.get("does_not_execute_trades") is True
        and readiness_receipt.get("does_not_modify_strategy_action") is True
    )
    local_receipts_safe = bool(
        readiness.get("schema_version") == "factor_universe_execution_readiness_audit.v1"
        and readiness_receipt.get("schema_version") == "factor_universe_execution_readiness_receipt.v1"
        and rank_zscore.get("schema_version") == "factor_universe_local_rank_zscore_dry_run.v1"
        and readiness.get("external_calls_triggered") is False
        and readiness_receipt.get("receipt_external_calls_triggered") is False
        and rank_zscore.get("external_calls_triggered") is False
    )
    production_done = bool(
        readiness.get("large_universe_pipeline_done")
        and readiness.get("cross_sectional_rank_zscore_done")
        and readiness.get("neutralization_done")
        and readiness.get("full_pool_validation_done")
        and readiness.get("production_factor_universe_complete")
    )
    missing_evidence_items = sorted(
        {
            "explicit_worker_batch_execution_evidence",
            "cross_sectional_rank_zscore_production_evidence",
            "neutralization_production_evidence",
            "factor_combination_research_evidence",
            "full_pool_validation_evidence",
            "provider_backed_validation_evidence",
            "production_promotion_marker",
            *[str(item) for item in readiness_receipt.get("missing_evidence_items", []) if item],
        }
    )
    rows = [
        _factor_universe_execution_activation_row(
            "readiness_receipt_visible",
            "passed_ready_for_worker_batch" if ready_for_worker_batch else "blocked_readiness_receipt",
            ready_for_worker_batch,
            f"readiness_receipt_status={readiness_receipt.get('status')}; allowed_next_step={readiness_receipt.get('allowed_next_step')}",
        ),
        _factor_universe_execution_activation_row(
            "read_plan_and_storage_contracts_ready",
            "passed_local_read_plan" if read_plan_ready and storage_ready else "blocked_read_plan_or_storage",
            read_plan_ready and storage_ready,
            f"task_plan_status={task_plan.get('status')}; storage_query_contract_consumed={storage_ready}; storage_query_contract_count={task_plan.get('storage_query_contract_count')}",
        ),
        _factor_universe_execution_activation_row(
            "explicit_worker_batch_task_required",
            "passed_requires_explicit_post_task",
            True,
            "Activation receipt does not create a task. Full-pool research must enter through a future explicit POST worker-batch task.",
        ),
        _factor_universe_execution_activation_row(
            "worker_batch_execution_evidence_required",
            "pending_not_executed_by_receipt",
            False,
            "No worker batch has been executed by this receipt; production evidence must come from a separate task result and call ledger.",
            blocks_production_completion=True,
        ),
        _factor_universe_execution_activation_row(
            "rank_zscore_production_evidence_required",
            "pending_local_dry_run_only",
            False,
            f"local_rank_zscore_status={rank_zscore.get('status')}; production rank/zscore remains false.",
            blocks_production_completion=True,
        ),
        _factor_universe_execution_activation_row(
            "neutralization_and_factor_combination_evidence_required",
            "pending_not_computed",
            False,
            "Industry/market-cap neutralization and factor-combination research remain future worker-backed validation items.",
            blocks_production_completion=True,
        ),
        _factor_universe_execution_activation_row(
            "full_pool_provider_validation_required",
            "pending_not_validated",
            False,
            "Full-pool/provider-backed validation is not complete and partial pools remain non-production evidence.",
            blocks_production_completion=True,
        ),
        _factor_universe_execution_activation_row(
            "frontend_cache_render_no_execution_boundary",
            "passed_read_only_boundary" if frontend_safe else "blocked_frontend_boundary",
            frontend_safe,
            f"page_render_starts_full_pool={readiness.get('page_render_starts_full_pool')}; frontend_computes_rank_zscore={readiness.get('frontend_computes_rank_zscore')}; partial_pool_is_full_market_proof={readiness.get('partial_pool_is_full_market_proof')}",
        ),
        _factor_universe_execution_activation_row(
            "local_no_provider_model_github_boundary",
            "passed_local_only" if local_receipts_safe else "blocked_external_boundary",
            local_receipts_safe,
            "Activation receipt reads local contracts only and cannot call provider/model/GitHub clients.",
        ),
        _factor_universe_execution_activation_row(
            "trade_and_action_boundary",
            "passed_no_trade_no_action" if trade_safe else "blocked_trade_boundary",
            trade_safe,
            "Universe research activation remains outside trades, strategy action, core action, evidence effects, and next-session projection.",
        ),
        _factor_universe_execution_activation_row(
            "production_completion_boundary",
            "pending_missing_worker_rank_neutralization_full_pool_evidence",
            production_done,
            f"production_done={production_done}; missing_evidence_items={missing_evidence_items}",
            blocks_production_completion=not production_done,
        ),
    ]
    production_blockers = [str(row["criterion"]) for row in rows if row["blocks_production_completion"] and not row["passed"]]
    activation_ready = bool(
        ready_for_worker_batch
        and read_plan_ready
        and storage_ready
        and worker_plan_ready
        and frontend_safe
        and trade_safe
        and local_receipts_safe
    )
    status = (
        "universe_execution_activation_ready_worker_batch_pending"
        if activation_ready
        else "universe_execution_activation_blocked_read_plan_or_boundary"
    )
    return {
        "schema_version": "factor_universe_execution_activation_receipt.v1",
        "status": status,
        "scope": "local_factor_universe_execution_activation_receipt_no_worker_or_provider_execution",
        "created_at": now,
        "ltg": "LTG-04/LTG-11",
        "local_activation_receipt_ready": activation_ready,
        "ready_for_explicit_worker_batch_task": activation_ready,
        "allowed_next_step": "explicit_post_task_factor_universe_worker_batch_research" if activation_ready else "repair_read_plan_storage_or_boundary_contracts",
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache worker batch execution",
            "React render full-pool research",
            "activation receipt creates worker task",
            "activation receipt starts worker process",
            "partial pool as full-market proof",
            "local rank/zscore dry-run as production research",
            "readiness receipt as production completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": missing_evidence_items,
        "read_plan_ready": read_plan_ready,
        "storage_query_contract_consumed": storage_ready,
        "worker_task_consumption_plan_ready": worker_plan_ready,
        "frontend_cache_render_no_execution_boundary": frontend_safe,
        "worker_batch_created_by_receipt": False,
        "worker_batch_executed_by_receipt": False,
        "rank_zscore_computed_by_receipt": False,
        "neutralization_computed_by_receipt": False,
        "provider_refresh_called_by_receipt": False,
        "large_universe_pipeline_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "full_pool_validation_done": False,
        "production_factor_universe_complete": False,
        "cache_get_external_calls": False,
        "activation_receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "row_count": len(rows),
        "production_blocker_count": len(production_blockers),
        "production_blockers": production_blockers,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_universe_execution_activation_receipt",
                "request_params_safe": {
                    "scope": "local_factor_universe_execution_activation_receipt_no_worker_or_provider_execution",
                    "ready_for_explicit_worker_batch_task": activation_ready,
                    "worker_batch_executed_by_receipt": False,
                    "production_factor_universe_complete": False,
                },
                "row_count": len(rows),
                "data_date": readiness_receipt.get("call_ledger", [{}])[0].get("data_date") if isinstance(readiness_receipt.get("call_ledger"), list) and readiness_receipt.get("call_ledger") else None,
                "local_fetched_at": now,
                "call_status": status,
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This activation receipt fixes LTG-04's next safe execution gate. It does not create tasks, start workers, compute full-pool metrics, call providers/models/GitHub, or trade.",
    }


def _attach_factor_universe_execution_activation_receipt(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _factor_universe_execution_activation_receipt(packet, now)
    packet["universe_execution_activation_receipt"] = receipt
    packet["universe_execution_activation_rows"] = list(receipt.get("rows") or [])
    contract = packet.get("universe_research_contract") if isinstance(packet.get("universe_research_contract"), dict) else {}
    if contract:
        contract = dict(contract)
        contract["universe_execution_activation_receipt_ready"] = bool(receipt.get("local_activation_receipt_ready"))
        contract["ready_for_explicit_worker_batch_task"] = bool(receipt.get("ready_for_explicit_worker_batch_task"))
        contract["worker_batch_executed_by_activation_receipt"] = False
        contract["production_factor_universe_complete"] = False
        contract["full_pool_validation_done"] = False
        packet["universe_research_contract"] = contract
    return packet, list(receipt.get("call_ledger") or [])


def _deepseek_explain_governance(*, payload: Any = None) -> dict[str, Any]:
    mode = get_deepseek_factor_explain_mode()
    configured_auto = get_deepseek_auto_explain_enabled(default=False)
    payload_auto = bool(payload.get("auto_after_task")) if isinstance(payload, dict) else False
    auto_after_task = mode == "auto_after_task" and configured_auto and payload_auto
    return {
        "mode": mode,
        "auto_after_task": auto_after_task,
        "configured_auto_after_task": configured_auto,
        "payload_auto_after_task_requested": payload_auto,
        "manual_task_allowed": mode != "disabled",
        "disabled": mode == "disabled",
        "model": _deepseek_model_strategy("factor_explain").get("model"),
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "cache_reads_never_call_deepseek": True,
        "react_render_never_calls_deepseek": True,
        "streamlit_render_never_calls_deepseek": True,
        "does_not_override_numeric_values": True,
        "does_not_modify_strategy_action": True,
    }


def _attach_deepseek_json_stability_audit(
    hub: dict[str, Any],
    *,
    prompt_preview: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    governance = dict(governance or _deepseek_explain_governance())
    hub["deepseek_explain_governance"] = governance
    prompt_preview = prompt_preview or _deepseek_prompt_preview(hub)
    explanation = hub.get("deepseek_explanation") if isinstance(hub.get("deepseek_explanation"), dict) else {
        "status": "not_called",
        "parse_failed": False,
        "model_call_status": "not_called",
        "token_estimate": 0,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
    }
    model_strategy = _deepseek_model_strategy("factor_explain")
    if validation_summary is None:
        validation_summary = hub.get("deepseek_validation_summary") if isinstance(hub.get("deepseek_validation_summary"), dict) else None
    if validation_summary is None:
        validation_summary = _deepseek_validation_summary(
            explanation=explanation,
            prompt_preview=prompt_preview,
            model_strategy=model_strategy,
        )
    audit = factor_research.build_factor_deepseek_json_stability_audit(
        prompt_preview=prompt_preview,
        validation_summary=validation_summary,
        governance=governance,
    )
    response_format_review = factor_research.build_factor_deepseek_response_format_review_contract(
        prompt_preview=prompt_preview,
        validation_summary=validation_summary,
        governance=governance,
        json_stability_audit=audit,
    )
    retry_repair_dry_run = factor_research.build_factor_deepseek_retry_repair_dry_run_contract(
        model_used=str(model_strategy.get("model") or "")
    )
    governance["json_stability_audit_status"] = audit["status"]
    governance["json_manual_explanation_ready"] = audit["manual_explanation_ready"]
    governance["json_production_ready"] = audit["production_ready"]
    governance["json_auto_after_task_ready"] = audit["auto_after_task_production_ready"]
    governance["response_format_review_status"] = response_format_review["status"]
    governance["response_format_production_ready"] = response_format_review["production_ready"]
    governance["response_format_retry_repair_ready"] = response_format_review["retry_repair_policy_ready"]
    governance["retry_repair_dry_run_status"] = retry_repair_dry_run["status"]
    governance["retry_repair_local_dry_run_ready"] = retry_repair_dry_run["local_retry_repair_dry_run_ready"]
    governance["bounded_retry_repair_ready"] = retry_repair_dry_run["bounded_retry_repair_ready"]
    hub["deepseek_explain_governance"] = governance
    hub["deepseek_validation_summary"] = validation_summary
    hub["deepseek_json_stability_audit"] = audit
    hub["deepseek_json_stability_rows"] = audit["rows"]
    hub["deepseek_response_format_review_contract"] = response_format_review
    hub["deepseek_response_format_review_rows"] = response_format_review["rows"]
    hub["deepseek_retry_repair_dry_run_contract"] = retry_repair_dry_run
    hub["deepseek_retry_repair_dry_run_rows"] = retry_repair_dry_run["rows"]
    return hub


def _deepseek_activation_row(criterion: str, status: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "deepseek_called": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _deepseek_production_activation_call_ledger(receipt: dict[str, Any], now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_deepseek_production_activation_receipt",
            "request_params_safe": {
                "status": receipt.get("status"),
                "allowed_next_step": receipt.get("allowed_next_step"),
                "provider_benchmark_done": receipt.get("provider_benchmark_done"),
                "production_deepseek_explanation_complete": receipt.get("production_deepseek_explanation_complete"),
            },
            "row_count": len(receipt.get("rows") or []),
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "activation_receipt_ready_provider_benchmark_pending",
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _deepseek_benchmark_recipe_row(
    phase_key: str,
    status: str,
    required_evidence: list[str],
    next_action: str,
    *,
    provider_model_execution_required: bool = True,
    promotion_gate: bool = False,
) -> dict[str, Any]:
    return {
        "phase_key": phase_key,
        "status": status,
        "recipe_step_ready": True,
        "provider_model_execution_required": bool(provider_model_execution_required),
        "promotion_gate": bool(promotion_gate),
        "required_evidence": required_evidence,
        "next_action": next_action,
        "model_call_status": "not_called",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
    }


def _deepseek_provider_benchmark_execution_recipe(
    hub: dict[str, Any],
    now: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    governance = hub.get("deepseek_explain_governance") if isinstance(hub.get("deepseek_explain_governance"), dict) else {}
    activation_receipt = (
        hub.get("deepseek_production_activation_receipt")
        if isinstance(hub.get("deepseek_production_activation_receipt"), dict)
        else {}
    )
    model_name = str(governance.get("model") or _deepseek_model_strategy("factor_explain").get("model") or "")
    required_sample_count = 40
    required_json_success_rate = 0.9
    max_retry_per_sample = 2
    rows = [
        _deepseek_benchmark_recipe_row(
            "explicit_user_approval",
            "recipe_ready_user_approval_required",
            ["user approval record", "benchmark scope ticket"],
            "Create an explicit benchmark task only after user approval binds model, sample count, prompt version, and response-format scope.",
            provider_model_execution_required=False,
        ),
        _deepseek_benchmark_recipe_row(
            "server_secret_preflight",
            "recipe_ready_secret_presence_check_required",
            ["server-side credential presence boolean", "no raw key name or value exposure"],
            "Check only credential presence before execution; never return token/key names, values, hashes, or lengths.",
            provider_model_execution_required=False,
        ),
        _deepseek_benchmark_recipe_row(
            "benchmark_sample_set",
            "recipe_ready_sample_set_required",
            [f">={required_sample_count} factor explanation samples", "mixed normal/missing/conflict/stale-like research contexts"],
            "Freeze a larger sample set that covers support, suppress, conflict, missing-data, and discipline-heavy packets.",
        ),
        _deepseek_benchmark_recipe_row(
            "provider_response_format",
            "recipe_ready_response_format_required",
            ["provider-level response_format/json_schema request", "six allowed top-level fields only"],
            "Execute with provider response-format enforcement, not prompt-only JSON wording.",
        ),
        _deepseek_benchmark_recipe_row(
            "bounded_retry_repair",
            "recipe_ready_retry_repair_required",
            [f"<= {max_retry_per_sample} bounded retries per sample", "repair/discard path recorded per failed parse"],
            "Use bounded repair only for parse failures; discard unsafe or illegal-field responses after the retry budget.",
        ),
        _deepseek_benchmark_recipe_row(
            "model_call_ledger",
            "recipe_ready_model_ledger_required",
            ["model_used", "status", "token_usage", "parse_status", "input_hash", "output_hash", "cache_hit_or_miss"],
            "Write a redacted model ledger for every sample and every retry without raw prompt secrets or token/key material.",
        ),
        _deepseek_benchmark_recipe_row(
            "sanitizer_parse_review",
            "recipe_ready_sanitizer_review_required",
            ["illegal fields ignored", "parse_failed payload discarded", "no numeric/action overwrite"],
            "Review sanitizer output after real responses and keep parse failures from contaminating packets.",
        ),
        _deepseek_benchmark_recipe_row(
            "token_budget_cost_review",
            "recipe_ready_cost_review_required",
            ["token totals", "per-sample average", "retry overhead", "cost estimate"],
            "Record token/cost evidence before any auto_after_task promotion.",
        ),
        _deepseek_benchmark_recipe_row(
            "auto_after_task_mode_gate",
            "recipe_ready_mode_gate_required",
            ["manual default-off preserved", "live_light opt-in only after benchmark promotion"],
            "Keep auto_after_task off until benchmark, response-format, retry/repair, cost, and promotion review pass.",
            promotion_gate=True,
        ),
        _deepseek_benchmark_recipe_row(
            "production_promotion_review",
            "recipe_ready_promotion_required",
            [f"JSON success rate > {required_json_success_rate:.0%}", "redaction review", "no action/numeric overwrite", "no trade execution"],
            "Promote only after direct provider benchmark evidence is reviewed; local recipe/dry-run evidence is not enough.",
            promotion_gate=True,
        ),
    ]
    phase_keys = [str(row["phase_key"]) for row in rows]
    recipe = {
        "schema_version": "factor_deepseek_provider_benchmark_execution_recipe.v1",
        "status": "deepseek_provider_benchmark_recipe_ready_model_execution_pending",
        "scope": "local_deepseek_provider_benchmark_recipe_no_model_call",
        "ltg": "LTG-07",
        "local_recipe_ready": activation_receipt.get("local_activation_receipt_ready") is True,
        "activation_receipt_status": activation_receipt.get("status"),
        "allowed_next_step": "explicit_deepseek_provider_benchmark_task_with_user_approval",
        "required_sample_count": required_sample_count,
        "required_json_success_rate": required_json_success_rate,
        "max_retry_per_sample": max_retry_per_sample,
        "model": model_name,
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "phase_count": len(rows),
        "phase_keys": phase_keys,
        "required_model_ledger_fields": [
            "model_used",
            "status",
            "token_usage",
            "parse_status",
            "cache_hit_or_miss",
            "input_hash",
            "output_hash",
        ],
        "allowed_output_fields": [
            "summary",
            "support_notes",
            "suppress_notes",
            "conflict_notes",
            "missing_data_notes",
            "discipline_notes",
        ],
        "not_allowed_next_steps": [
            "GET cache model call",
            "React render model call",
            "local retry/repair dry-run as provider benchmark",
            "provider benchmark without response_format",
            "benchmark recipe as production completion",
            "auto_after_task default-on promotion",
            "raw token/key in prompt, ledger, packet, cache, or log",
            "DeepSeek numeric/action overwrite",
        ],
        "missing_evidence": [
            f"provider benchmark report with at least {required_sample_count} samples",
            "provider response_format/json_schema execution evidence",
            "per-sample model ledger with token usage and hashes",
            "bounded retry/repair execution ledger",
            "sanitizer and parse-failed discard review",
            "token budget and cost evidence",
            "redaction review",
            "manual production promotion review",
        ],
        "provider_benchmark_done": False,
        "larger_benchmark_done": False,
        "provider_response_format_enforced": False,
        "bounded_retry_repair_ready": False,
        "token_budget_cost_evidence_complete": False,
        "auto_after_task_production_ready": False,
        "production_deepseek_explanation_complete": False,
        "provider_model_called_by_recipe": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
        "rows": rows,
    }
    ledger = [
        {
            "api": "local_deepseek_provider_benchmark_execution_recipe",
            "request_params_safe": {
                "status": recipe["status"],
                "allowed_next_step": recipe["allowed_next_step"],
                "required_sample_count": required_sample_count,
                "required_json_success_rate": required_json_success_rate,
                "provider_benchmark_done": False,
            },
            "row_count": len(rows),
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "benchmark_recipe_ready_model_execution_pending",
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]
    return recipe, rows, ledger


def _attach_deepseek_provider_benchmark_execution_recipe(
    hub: dict[str, Any],
    now: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recipe, rows, ledger = _deepseek_provider_benchmark_execution_recipe(hub, now)
    hub["deepseek_provider_benchmark_execution_recipe"] = recipe
    hub["deepseek_provider_benchmark_execution_rows"] = rows
    governance = hub.get("deepseek_explain_governance")
    if isinstance(governance, dict):
        governance["provider_benchmark_execution_recipe_status"] = recipe["status"]
        governance["provider_benchmark_execution_recipe_ready"] = recipe["local_recipe_ready"]
        governance["provider_benchmark_required_sample_count"] = recipe["required_sample_count"]
    return hub, ledger


def _attach_deepseek_production_activation_receipt(
    hub: dict[str, Any],
    now: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    governance = hub.get("deepseek_explain_governance") if isinstance(hub.get("deepseek_explain_governance"), dict) else {}
    validation = hub.get("deepseek_validation_summary") if isinstance(hub.get("deepseek_validation_summary"), dict) else {}
    json_audit = hub.get("deepseek_json_stability_audit") if isinstance(hub.get("deepseek_json_stability_audit"), dict) else {}
    response_review = (
        hub.get("deepseek_response_format_review_contract")
        if isinstance(hub.get("deepseek_response_format_review_contract"), dict)
        else {}
    )

    local_governance_ready = (
        governance.get("mode") in {"manual_only", "disabled"}
        and governance.get("manual_task_allowed") is True
        and governance.get("auto_after_task") is False
        and governance.get("configured_auto_after_task") is False
        and governance.get("cache_reads_never_call_deepseek") is True
        and governance.get("react_render_never_calls_deepseek") is True
        and validation.get("model_call_status") == "not_called"
    )
    sanitizer_ready = (
        validation.get("validation_mode") == "local_sanitizer_only"
        and validation.get("does_not_override_numeric_values") is True
        and validation.get("does_not_output_strategy_action") is True
    )
    json_local_ready = (
        json_audit.get("schema_version") == "factor_deepseek_json_stability_audit.v1"
        and json_audit.get("manual_explanation_ready") is True
        and json_audit.get("production_ready") is False
    )
    response_local_ready = (
        response_review.get("schema_version") == "factor_deepseek_response_format_review_contract.v1"
        and response_review.get("local_response_format_review_ready") is True
        and response_review.get("production_ready") is False
    )

    rows = [
        _deepseek_activation_row(
            "manual_default_off_governance_ready",
            "passed_manual_default_off",
            local_governance_ready,
            "manual_only/disabled governance is visible; cache reads and React render do not call DeepSeek.",
        ),
        _deepseek_activation_row(
            "sanitizer_whitelist_ready",
            "passed_sanitizer_whitelist",
            sanitizer_ready,
            "Only whitelisted explanation fields may survive; numeric, action, price, position, and operation-zone fields remain blocked.",
        ),
        _deepseek_activation_row(
            "local_json_stability_audit_ready",
            "passed_local_audit_production_blocked",
            json_local_ready,
            "Local JSON stability audit is present and still blocks production automation.",
        ),
        _deepseek_activation_row(
            "response_format_review_ready",
            "passed_local_review_provider_enforcement_pending",
            response_local_ready,
            "Local response-format review is ready, while provider-level response_format enforcement remains pending.",
        ),
        _deepseek_activation_row(
            "provider_benchmark_required",
            "pending_provider_benchmark",
            False,
            "A larger provider-backed benchmark with JSON success rate above 90% is still required.",
        ),
        _deepseek_activation_row(
            "provider_response_format_enforcement_required",
            "pending_provider_response_format",
            False,
            "Provider response_format/json_schema enforcement must be proven with real responses before production promotion.",
        ),
        _deepseek_activation_row(
            "bounded_retry_repair_required",
            "pending_retry_repair",
            False,
            "Bounded retry/repair behavior must be implemented and evaluated before auto explanation can be production-ready.",
        ),
        _deepseek_activation_row(
            "token_budget_cost_evidence_required",
            "pending_token_budget",
            False,
            "Token/cost budget evidence must be durable and predictable across benchmark samples.",
        ),
        _deepseek_activation_row(
            "auto_after_task_activation_required",
            "pending_auto_after_task_activation",
            False,
            "auto_after_task must remain default-off until provider benchmark, response-format enforcement, retry/repair, and cost evidence pass.",
        ),
        _deepseek_activation_row(
            "no_get_or_render_model_call_boundary",
            "passed_no_get_or_render_model_call",
            True,
            "The receipt is built from cache state only and does not call DeepSeek from GET cache or React render.",
        ),
        _deepseek_activation_row(
            "no_numeric_action_overwrite_boundary",
            "passed_no_numeric_action_overwrite",
            True,
            "DeepSeek output cannot overwrite prices, positions, factor values, operation zones, or strategy action.",
        ),
    ]

    blockers = [row["criterion"] for row in rows if not row["passed"]]
    receipt = {
        "schema_version": "deepseek_production_activation_receipt.v1",
        "status": "deepseek_activation_receipt_ready_provider_benchmark_pending",
        "scope": "local_deepseek_production_activation_receipt_no_model_call",
        "ltg": "LTG-07",
        "local_activation_receipt_ready": local_governance_ready and sanitizer_ready and json_local_ready and response_local_ready,
        "manual_explanation_ready": bool(json_audit.get("manual_explanation_ready") or response_review.get("manual_explanation_ready")),
        "provider_benchmark_done": False,
        "larger_benchmark_done": False,
        "provider_response_format_enforced": False,
        "response_format_enforced": False,
        "retry_repair_policy_ready": False,
        "bounded_retry_repair_ready": False,
        "token_budget_cost_evidence_complete": False,
        "auto_after_task_production_ready": False,
        "production_deepseek_explanation_complete": False,
        "allowed_next_step": "explicit_provider_benchmark_then_response_format_enforcement_retry_repair_cost_review",
        "not_allowed_next_steps": [
            "GET cache model call",
            "React render model call",
            "sanitizer as provider benchmark",
            "local JSON audit as production completion",
            "response-format review as provider enforcement",
            "auto_after_task default-on promotion",
            "DeepSeek numeric/action overwrite",
        ],
        "missing_evidence": [
            "provider benchmark JSON success rate > 90%",
            "provider response_format/json_schema enforcement evidence",
            "bounded retry/repair evaluation",
            "token budget and cost evidence",
            "durable provider call ledger evidence",
            "manual promotion review for auto_after_task",
        ],
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "provider_model_called_by_receipt": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "receipt_external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
        "rows": rows,
    }
    ledger = _deepseek_production_activation_call_ledger(receipt, now)
    receipt["call_ledger"] = ledger
    hub["deepseek_production_activation_receipt"] = receipt
    hub["deepseek_production_activation_rows"] = rows
    return hub, ledger


def _factor_universe_cache_part(hub: dict[str, Any]) -> dict[str, Any]:
    universe = hub.get("universe") if isinstance(hub.get("universe"), dict) else {}
    items = universe.get("items") if isinstance(universe.get("items"), list) else []
    return {
        "universe_type": universe.get("type") or "unknown",
        "items": [str(item) for item in items[:12]],
        "size": universe.get("size") if universe.get("size") is not None else len(items),
    }


def _deepseek_explanation_cache_key(hub: dict[str, Any], *, input_hash: str, model_name: str) -> dict[str, Any]:
    return {
        "module": "factor_quant_hub",
        **_factor_universe_cache_part(hub),
        "ts_code": (_factor_universe_cache_part(hub).get("items") or [""])[0],
        "trade_date": hub.get("trade_date") or hub.get("data_date") or "",
        "input_hash": input_hash,
        "model_name": model_name,
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
    }


def _same_deepseek_cache_key(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _score_items(score: dict[str, Any], key: str) -> list[Any]:
    items = score.get(key)
    return items if isinstance(items, list) else []


def _factor_score_chart_payload(packet: dict[str, Any]) -> dict[str, Any]:
    score = packet.get("score") if isinstance(packet.get("score"), dict) else {}
    buckets = [
        ("support", "支持", "support_factors"),
        ("suppress", "压制", "suppress_factors"),
        ("neutral", "中性", "neutral_factors"),
        ("missing", "缺失", "missing_factors"),
        ("conflict", "冲突", "conflict_factors"),
    ]
    bucket_rows = [
        {
            "bucket_key": bucket_key,
            "bucket_label": label,
            "count": len(_score_items(score, score_key)),
            "source_field": f"score.{score_key}",
        }
        for bucket_key, label, score_key in buckets
    ]
    return {
        "status": "ready" if score else "missing",
        "source_packet": packet.get("packet_key") or "command_center_factor_quant_hub_packet",
        "renderer": "ECharts",
        "chart_type": "factor_score_bucket_bar",
        "bucket_rows": bucket_rows,
        "x_axis_labels": [row["bucket_label"] for row in bucket_rows],
        "series": [
            {
                "name": "因子桶数量",
                "type": "bar",
                "data": [row["count"] for row in bucket_rows],
            }
        ],
        "chart_contract": {
            "contract_key": "factor_quant_score_echarts_payload",
            "schema_version": "factor_quant_score_echarts_payload.v1",
            "renderer": "ECharts",
            "cache_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "frontend_computes_trade_action": False,
            "does_not_modify_action": True,
            "does_not_modify_next_session_projection": True,
            "does_not_modify_operation_zones": True,
            "does_not_modify_factor_score": True,
            "series_counts": {
                "bucket_rows": len(bucket_rows),
                "support": bucket_rows[0]["count"],
                "suppress": bucket_rows[1]["count"],
                "neutral": bucket_rows[2]["count"],
                "missing": bucket_rows[3]["count"],
                "conflict": bucket_rows[4]["count"],
            },
            "guardrails": [
                "GET /api/factor-quant/cache 不触发 Tushare、DeepSeek 或 GitHub。",
                "React/ECharts 只读渲染 score buckets，不计算或覆盖交易动作。",
                "因子图表不执行真实交易，不读取或展示 token/key。",
                "因子图表不得修改 strategy action、次日图谱、operation_zones 或 composite_score。",
            ],
        },
        "warnings": [
            "多因子柱状图只展示 score bucket 数量，不是交易建议。",
            "缺失因子只进入 missing bucket，不得作为 suppress 或卖出理由。",
        ],
    }


def _factor_quant_cache_call_ledger(packet: dict[str, Any], now: str) -> list[dict[str, Any]]:
    runtime = packet.get("runtime") if isinstance(packet.get("runtime"), dict) else {}
    values = runtime.get("factor_values") if isinstance(runtime.get("factor_values"), list) else []
    return [
        {
            "api": "local_factor_quant_cache",
            "request_params_safe": {
                "packet_key": packet.get("packet_key"),
                "mode": packet.get("mode"),
                "status": packet.get("status"),
                "cache_source": packet.get("cache_source"),
                "runtime_status": runtime.get("status"),
            },
            "row_count": len(values),
            "data_date": packet.get("trade_date") or packet.get("data_date"),
            "local_fetched_at": now,
            "call_status": "cache_missing" if packet.get("status") == "cache_missing" else "cache_read",
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _factor_test_storage_query_consumption(now: str) -> dict[str, Any]:
    storage_packet = storage_service.factor_values_status(limit=10)
    contract = storage_packet.get("query_result_contract") if isinstance(storage_packet.get("query_result_contract"), dict) else {}
    page_info = storage_packet.get("page_info") if isinstance(storage_packet.get("page_info"), dict) else {}
    query = storage_packet.get("query") if isinstance(storage_packet.get("query"), dict) else {}
    policy = storage_packet.get("query_service_policy") if isinstance(storage_packet.get("query_service_policy"), dict) else {}
    projected_columns = storage_packet.get("projected_columns") if isinstance(storage_packet.get("projected_columns"), list) else []
    missing_projected_columns = storage_packet.get("missing_projected_columns") if isinstance(storage_packet.get("missing_projected_columns"), list) else []
    applied_filters = storage_packet.get("applied_filters") if isinstance(storage_packet.get("applied_filters"), list) else []
    skipped_filters = storage_packet.get("skipped_filters") if isinstance(storage_packet.get("skipped_filters"), list) else []
    returned_row_count = int(page_info.get("returned_row_count") or storage_packet.get("row_count") or 0)
    query_status = str(contract.get("status") or storage_packet.get("status") or "missing")
    return {
        "status": "query_contract_consumed" if contract else "query_contract_missing",
        "schema_version": "factor_test_storage_query_consumption.v1",
        "consumer": "Factor Test Lab",
        "dataset": "factor_values",
        "source_endpoint": "GET /api/storage/factor-values",
        "query_wrapper": storage_packet.get("query_wrapper") or query.get("query_wrapper") or "duckdb_filtered_parquet.v1",
        "query_result_contract_schema_version": contract.get("schema_version") or "duckdb_query_result_contract.v1",
        "storage_status": storage_packet.get("status") or query_status,
        "query_status": query_status,
        "storage_row_count": int(storage_packet.get("row_count") or 0),
        "returned_row_count": returned_row_count,
        "sample_row_limit": 10,
        "projected_columns": projected_columns,
        "missing_projected_columns": missing_projected_columns,
        "projection_requested": True,
        "typed_projection_consumed": bool(policy.get("typed_projection_enabled", True)),
        "query_result_contract_consumed": bool(contract),
        "cursor_pagination_consumed": bool(page_info),
        "page_info": {
            "limit": page_info.get("limit"),
            "cursor": page_info.get("cursor") or "",
            "cursor_status": page_info.get("cursor_status") or "not_provided",
            "offset": page_info.get("offset") or 0,
            "has_more": bool(page_info.get("has_more")),
            "next_cursor": page_info.get("next_cursor") or "",
            "returned_row_count": returned_row_count,
        },
        "applied_filters": applied_filters,
        "skipped_filters": skipped_filters,
        "metrics_computed_from_storage_query": False,
        "storage_query_enters_strategy_action": False,
        "full_market_validation_done": False,
        "real_small_pool_validation_done": False,
        "cache_only": True,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "auto_refresh_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Factor Test Lab 当前只消费 factor_values DuckDB 查询合同；不把本地查询样本当作 IC/Rank IC/ICIR 生产验收。",
        "call_ledger": [
            {
                "api": "local_factor_test_storage_query_consumption",
                "request_params_safe": {
                    "dataset": "factor_values",
                    "limit": 10,
                    "source_endpoint": "GET /api/storage/factor-values",
                    "query_wrapper": storage_packet.get("query_wrapper") or query.get("query_wrapper") or "duckdb_filtered_parquet.v1",
                },
                "row_count": returned_row_count,
                "data_date": None,
                "local_fetched_at": now,
                "call_status": query_status,
                "error_message_safe": str(storage_packet.get("error_message_safe") or query.get("error_message_safe") or "")[:240],
                **_local_ledger_boundary(),
            }
        ],
    }


def _attach_factor_test_storage_query_consumption(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    consumption = _factor_test_storage_query_consumption(now)
    factor_tests["storage_query_consumption"] = consumption
    factor_tests["storage_query_consumption_rows"] = [
        {
            "dataset": consumption["dataset"],
            "status": consumption["status"],
            "storage_status": consumption["storage_status"],
            "query_status": consumption["query_status"],
            "query_wrapper": consumption["query_wrapper"],
            "projected_columns": ",".join(str(item) for item in consumption["projected_columns"]),
            "missing_projected_columns": ",".join(str(item) for item in consumption["missing_projected_columns"]),
            "returned_row_count": consumption["returned_row_count"],
            "next_cursor": consumption["page_info"]["next_cursor"],
            "metrics_computed_from_storage_query": consumption["metrics_computed_from_storage_query"],
            "storage_query_enters_strategy_action": consumption["storage_query_enters_strategy_action"],
            "external_calls_triggered": consumption["external_calls_triggered"],
        }
    ]
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(consumption.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["storage_query_contract_consumed"] = consumption["query_result_contract_consumed"]
        acceptance["storage_query_metrics_computed"] = False
        acceptance["storage_query_enters_strategy_action"] = False
        acceptance["does_not_call_tushare"] = True
        acceptance["does_not_call_deepseek"] = True
        acceptance["does_not_call_github"] = True
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(consumption.get("call_ledger") or [])


def _factor_test_local_dataset_sample_evidence(now: str) -> dict[str, Any]:
    sample_limit = 1000
    dataset_names = ("factor_values", "daily", "daily_basic", "moneyflow", "trade_cal")
    datasets: dict[str, dict[str, Any]] = {}
    for dataset in dataset_names:
        try:
            datasets[dataset] = storage_service.parquet_dataset_status(dataset, limit=sample_limit)
        except Exception as exc:
            datasets[dataset] = {
                "status": "read_failed",
                "dataset": dataset,
                "row_count": 0,
                "metadata": {},
                "query": {"rows": []},
                "error_message_safe": str(exc).splitlines()[0][:240],
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }

    factor_packet = datasets.get("factor_values") or {}
    factor_rows = _storage_query_rows(factor_packet)
    factor_row_count = _storage_total_or_returned_row_count(factor_packet)
    unique_tickers = sorted({str(row.get("ts_code") or "") for row in factor_rows if str(row.get("ts_code") or "").strip()})
    unique_trade_dates = sorted({str(row.get("trade_date") or "") for row in factor_rows if str(row.get("trade_date") or "").strip()})
    unique_factor_keys = sorted({str(row.get("factor_key") or "") for row in factor_rows if str(row.get("factor_key") or "").strip()})
    usable_factor_values = [
        row
        for row in factor_rows
        if _is_finite_number(row.get("raw_value"))
        and str(row.get("data_status") or "").lower() not in {"missing", "expired", "stale", "historical", "unknown"}
    ]
    forward_return_keys = {"forward_return", "forward_return_1d", "forward_return_5d", "future_return", "label_return"}
    forward_return_sample_count = sum(
        1
        for row in factor_rows
        if any(_is_finite_number(row.get(key)) for key in forward_return_keys)
    )
    market_rows = [
        {
            "dataset": name,
            "status": packet.get("status") or "missing",
            "row_count": _storage_total_or_returned_row_count(packet),
            "returned_row_count": int(packet.get("row_count") or 0),
            "metadata_row_count": _metadata_row_count(packet),
        }
        for name, packet in datasets.items()
        if name != "factor_values"
    ]
    market_dataset_ready_count = sum(1 for row in market_rows if row["status"] == "ready" and row["row_count"] > 0)
    latest_factor_trade_date = unique_trade_dates[-1] if unique_trade_dates else None

    def _row(
        criterion: str,
        status: str,
        evidence: str,
        next_action: str,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "required_for_real_small_pool_validation": required,
            "blocks_real_small_pool_validation": bool(required and status != "passed"),
            "evidence": evidence,
            "next_action": next_action,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "factor_values_dataset_present",
            "passed" if factor_packet.get("status") == "ready" and factor_row_count > 0 else "blocked",
            f"factor_values_status={factor_packet.get('status')}; row_count={factor_row_count}; returned_sample={len(factor_rows)}",
            "Run a future button-gated local/provider-backed research sample task before computing production Factor Test metrics.",
        ),
        _row(
            "market_datasets_present",
            "passed" if market_dataset_ready_count == len(market_rows) else "blocked",
            f"ready_market_dataset_count={market_dataset_ready_count}/{len(market_rows)}; rows={market_rows}",
            "Populate daily, daily_basic, moneyflow, and trade_cal through approved task pipelines before small-pool validation.",
        ),
        _row(
            "small_pool_ticker_count",
            "passed" if len(unique_tickers) >= 5 else "blocked",
            f"unique_factor_ticker_count={len(unique_tickers)}; required>=5",
            "Collect at least a small cross-section of tickers before treating the sample as real small-pool research.",
        ),
        _row(
            "sample_window_depth",
            "passed" if len(unique_trade_dates) >= 20 else "blocked",
            f"unique_factor_trade_date_count={len(unique_trade_dates)}; required>=20",
            "Collect a deeper trade-date window before validating rolling IC, decay, and out-of-sample behavior.",
        ),
        _row(
            "usable_factor_values",
            "passed" if len(usable_factor_values) >= 100 else "blocked",
            f"usable_factor_value_count={len(usable_factor_values)}; required>=100; factor_key_count={len(unique_factor_keys)}",
            "Keep missing/stale/historical rows out of metric samples and build enough usable factor values first.",
        ),
        _row(
            "forward_return_sample",
            "passed" if forward_return_sample_count > 0 else "blocked",
            f"forward_return_sample_count={forward_return_sample_count}",
            "Add explicit forward-return labels in a future research task before computing IC from local datasets.",
        ),
        _row(
            "provider_backed_sample",
            "pending_provider_validation",
            "No provider-backed small-pool sample is executed by GET factor cache.",
            "Run a future explicit POST task with call_ledger before marking provider-backed small-pool validation done.",
        ),
        _row(
            "storage_query_not_metric_source",
            "passed",
            "Local dataset rows are counted for sufficiency only; no IC, Rank IC, ICIR, group return, or action is computed from them.",
            "Keep this evidence as a readiness audit until a separate research task builds validated metric samples.",
        ),
        _row(
            "trade_action_isolation",
            "passed",
            "Local dataset sample evidence does not execute trades, mutate action, or modify next-session projection.",
            "Preserve Factor Test outputs as research-only unless a separate approved trading design exists.",
        ),
        _row(
            "external_call_boundary",
            "passed",
            "This evidence reads local Parquet/DuckDB contracts only and does not call Tushare, DeepSeek, or GitHub.",
            "Keep provider-backed refresh and explanation calls behind explicit POST task or button gates.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_real_small_pool_validation"]]
    local_sufficiency_blocking_rows = [
        row for row in blocking_rows if row["criterion"] != "provider_backed_sample"
    ]
    pending_rows = [row for row in rows if str(row["status"]).startswith("pending")]
    local_dataset_sample_available = factor_packet.get("status") == "ready" and factor_row_count > 0
    status = (
        "local_dataset_sample_ready_research_only_provider_validation_pending"
        if local_dataset_sample_available and not local_sufficiency_blocking_rows
        else (
            "local_dataset_sample_blocked_not_enough_data"
            if local_dataset_sample_available
            else "local_dataset_sample_missing"
        )
    )
    return {
        "schema_version": "factor_test_local_dataset_sample_evidence.v1",
        "status": status,
        "scope": "local_parquet_sample_sufficiency_audit_not_metric_validation",
        "created_at": now,
        "sample_limit_per_dataset": sample_limit,
        "dataset_count": len(datasets),
        "factor_values_status": factor_packet.get("status") or "missing",
        "factor_values_row_count": factor_row_count,
        "factor_values_returned_sample_count": len(factor_rows),
        "unique_factor_ticker_count": len(unique_tickers),
        "unique_factor_trade_date_count": len(unique_trade_dates),
        "factor_key_count": len(unique_factor_keys),
        "usable_factor_value_count": len(usable_factor_values),
        "forward_return_sample_count": forward_return_sample_count,
        "market_dataset_ready_count": market_dataset_ready_count,
        "market_dataset_count": len(market_rows),
        "market_dataset_rows": market_rows,
        "latest_factor_trade_date": latest_factor_trade_date,
        "local_dataset_sample_available": local_dataset_sample_available,
        "local_dataset_sample_sufficiency_done": local_dataset_sample_available and not local_sufficiency_blocking_rows,
        "metrics_computed_from_local_dataset": False,
        "storage_query_rows_used_as_metrics": False,
        "real_small_pool_validation_done": False,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "cache_only": True,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "auto_refresh_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "criterion_count": len(rows),
        "pending_criterion_count": len(pending_rows),
        "blocking_criterion_count": len(blocking_rows),
        "passed_criterion_count": len(rows) - len(blocking_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocking_rows],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_local_dataset_sample_evidence",
                "request_params_safe": {
                    "datasets": list(dataset_names),
                    "sample_limit_per_dataset": sample_limit,
                    "scope": "local_parquet_sample_sufficiency_audit_not_metric_validation",
                    "provider_backed_small_pool_validation_done": False,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": factor_row_count,
                "data_date": latest_factor_trade_date,
                "local_fetched_at": now,
                "call_status": status,
                "error_message_safe": str(factor_packet.get("error_message_safe") or "")[:240],
                **_local_ledger_boundary(),
            }
        ],
        "note": "This local evidence counts dataset sufficiency only. It does not compute production Factor Test metrics, call providers, or prove real small-pool/full-market validation.",
    }


def _attach_factor_test_local_dataset_sample_evidence(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    evidence = _factor_test_local_dataset_sample_evidence(now)
    factor_tests["local_dataset_sample_evidence"] = evidence
    factor_tests["local_dataset_sample_evidence_rows"] = list(evidence.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(evidence.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["local_dataset_sample_evidence_ready"] = True
        acceptance["local_dataset_sample_available"] = evidence["local_dataset_sample_available"]
        acceptance["local_dataset_sample_sufficiency_done"] = evidence["local_dataset_sample_sufficiency_done"]
        acceptance["local_dataset_sample_metrics_computed"] = False
        acceptance["local_dataset_rows_used_as_metrics"] = False
        acceptance["real_small_pool_validation_done"] = False
        acceptance["provider_backed_small_pool_validation_done"] = False
        acceptance["full_market_validation_done"] = False
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(evidence.get("call_ledger") or [])


def _storage_query_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    query = packet.get("query") if isinstance(packet.get("query"), dict) else {}
    rows = query.get("rows") if isinstance(query.get("rows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _metadata_row_count(packet: dict[str, Any]) -> int:
    metadata = packet.get("metadata") if isinstance(packet.get("metadata"), dict) else {}
    try:
        return int(metadata.get("row_count_metadata") or 0)
    except (TypeError, ValueError):
        return 0


def _storage_total_or_returned_row_count(packet: dict[str, Any]) -> int:
    metadata_count = _metadata_row_count(packet)
    if metadata_count:
        return metadata_count
    try:
        return int(packet.get("row_count") or 0)
    except (TypeError, ValueError):
        return 0


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _factor_test_production_validation_qa_contract(factor_tests: dict[str, Any], now: str) -> dict[str, Any]:
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    small_pool = factor_tests.get("small_pool_acceptance") if isinstance(factor_tests.get("small_pool_acceptance"), dict) else {}
    storage_query = factor_tests.get("storage_query_consumption") if isinstance(factor_tests.get("storage_query_consumption"), dict) else {}

    def _row(
        criterion: str,
        status: str,
        evidence: str,
        next_action: str,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "required_for_production_validation": required,
            "blocks_production_validation": bool(required and status != "passed"),
            "evidence": evidence,
            "next_action": next_action,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    local_light_ready = bool(small_pool.get("local_light_observation_acceptance_done"))
    storage_query_safe = bool(
        storage_query.get("query_result_contract_consumed")
        and not storage_query.get("metrics_computed_from_storage_query")
        and not storage_query.get("storage_query_enters_strategy_action")
    )
    state_contract_safe = bool(
        acceptance.get("all_result_states_are_research_only", True)
        and acceptance.get("research_pass_is_not_trade_signal", True)
        and not acceptance.get("enters_core_action", False)
    )
    rows = [
        _row(
            "local_light_metrics_readiness",
            "passed" if local_light_ready else "blocked",
            f"small_pool_status={small_pool.get('status')}; local_light_observation_acceptance_done={local_light_ready}",
            "Keep local light metrics visible, but do not claim provider-backed small-pool validation from this result.",
        ),
        _row(
            "provider_backed_small_pool_sample",
            "pending_provider_validation",
            "No provider-backed target sample has been validated in this cache read.",
            "Run a future button-gated provider-backed small-pool validation task with call_ledger and safe failure states.",
        ),
        _row(
            "multi_horizon_forward_returns",
            "pending_research_validation",
            "Current light metrics do not prove multi-horizon forward-return stability.",
            "Validate multiple forward-return horizons before promoting Factor Test Lab to production research.",
        ),
        _row(
            "rolling_window_ic_icir",
            "pending_research_validation",
            "Current local packet does not prove rolling IC / Rank IC / ICIR across windows.",
            "Add rolling-window IC/ICIR validation on provider-backed small pools or full universes.",
        ),
        _row(
            "out_of_sample_decay",
            "pending_research_validation",
            "Current local readiness does not prove out-of-sample stability or recent decay.",
            "Add sample split and recent-decay acceptance before production validation.",
        ),
        _row(
            "transaction_cost_assumptions",
            "pending_research_validation",
            "Cost-adjusted light metrics are not a production-grade transaction cost model.",
            "Validate turnover, slippage, fees, and cost-after-return assumptions on target samples.",
        ),
        _row(
            "neutralization_stability",
            "pending_research_validation",
            "Industry and market-cap neutral stability needs larger provider-backed samples.",
            "Validate neutral IC stability across industry and size buckets.",
        ),
        _row(
            "pit_lookahead_survivorship_controls",
            "pending_research_validation",
            "Current local contract does not prove point-in-time, lookahead, or survivorship controls on real samples.",
            "Add PIT/lookahead/survivorship checks to the future validation task.",
        ),
        _row(
            "storage_query_not_metric_source",
            "passed" if storage_query_safe else "blocked",
            "storage query contract is consumed without computing metrics or entering strategy action.",
            "Keep storage query rows as metadata until explicit research sample construction is implemented.",
        ),
        _row(
            "state_transition_research_only",
            "passed" if state_contract_safe else "blocked",
            "research_pass/watchlist/disabled/invalid/not_enough_data remain research labels.",
            "Preserve research-only state transitions and prevent promotion into action or evidence execution paths.",
        ),
        _row(
            "trade_action_isolation",
            "passed",
            "Factor Test Lab validation contract does not execute trades, mutate action, or modify next-session projection.",
            "Keep any future factor validation outputs outside strategy action unless a separate approved trading design exists.",
        ),
        _row(
            "external_call_boundary",
            "passed",
            "GET factor cache builds this QA contract locally and does not call Tushare, DeepSeek, or GitHub.",
            "Future provider-backed validation must be button/task gated and recorded in call_ledger.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_production_validation"]]
    pending_rows = [row for row in rows if str(row["status"]).startswith("pending")]
    return {
        "schema_version": "factor_test_production_validation_qa_contract.v1",
        "status": "production_validation_qa_contract_ready_provider_execution_pending",
        "scope": "local_factor_test_validation_contract_not_provider_backed_execution",
        "created_at": now,
        "criterion_count": len(rows),
        "pending_criterion_count": len(pending_rows),
        "blocking_criterion_count": len(blocking_rows),
        "passed_criterion_count": len(rows) - len(blocking_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocking_rows],
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "local_light_observation_acceptance_done": local_light_ready,
        "storage_query_contract_consumed": bool(storage_query.get("query_result_contract_consumed")),
        "storage_query_rows_used_as_metrics": False,
        "state_transition_research_only": state_contract_safe,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_production_validation_qa_contract",
                "request_params_safe": {
                    "scope": "local_factor_test_validation_contract_not_provider_backed_execution",
                    "provider_backed_small_pool_validation_done": False,
                    "full_market_validation_done": False,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": now,
                "call_status": "contract_ready_provider_execution_pending",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This QA contract makes future production Factor Test Lab validation explicit. It does not run provider-backed samples, full-market research, external calls, or trade actions.",
    }


def _attach_factor_test_production_validation_qa_contract(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    contract = _factor_test_production_validation_qa_contract(factor_tests, now)
    factor_tests["production_validation_qa_contract"] = contract
    factor_tests["production_validation_qa_rows"] = list(contract.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(contract.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["production_validation_qa_contract_ready"] = True
        acceptance["production_factor_test_validation_complete"] = False
        acceptance["provider_backed_small_pool_validation_done"] = False
        acceptance["full_market_validation_done"] = False
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(contract.get("call_ledger") or [])


def _factor_test_provider_validation_blocker_row(
    phase: str,
    status: str,
    passed: bool,
    evidence: str,
    next_action: str,
    *,
    blockers: list[str] | None = None,
    production_blocker: bool | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool((not passed) if production_blocker is None else production_blocker),
        "blockers": blockers or [],
        "blocker_count": len(blockers or []),
        "evidence": evidence,
        "next_action": next_action,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
    }


def _factor_test_provider_validation_blocker_audit(factor_tests: dict[str, Any], now: str) -> dict[str, Any]:
    storage_query = factor_tests.get("storage_query_consumption") if isinstance(factor_tests.get("storage_query_consumption"), dict) else {}
    local_dataset = factor_tests.get("local_dataset_sample_evidence") if isinstance(factor_tests.get("local_dataset_sample_evidence"), dict) else {}
    small_pool = factor_tests.get("small_pool_acceptance") if isinstance(factor_tests.get("small_pool_acceptance"), dict) else {}
    production_qa = factor_tests.get("production_validation_qa_contract") if isinstance(factor_tests.get("production_validation_qa_contract"), dict) else {}
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}

    storage_query_safe = bool(
        storage_query.get("schema_version") == "factor_test_storage_query_consumption.v1"
        and storage_query.get("metrics_computed_from_storage_query") is False
        and storage_query.get("storage_query_enters_strategy_action") is False
        and storage_query.get("writes_parquet_on_get") is False
        and storage_query.get("auto_refresh_on_get") is False
    )
    local_dataset_sufficient = bool(local_dataset.get("local_dataset_sample_sufficiency_done"))
    local_light_ready = bool(small_pool.get("local_light_observation_acceptance_done"))
    production_rows = production_qa.get("rows") if isinstance(production_qa.get("rows"), list) else []
    production_blocking_criteria = [str(row.get("criterion")) for row in production_rows if isinstance(row, dict) and row.get("blocks_production_validation")]
    provider_sample_done = bool(production_qa.get("provider_backed_small_pool_validation_done"))
    full_market_done = bool(production_qa.get("full_market_validation_done"))
    trade_isolated = bool(
        production_qa.get("does_not_execute_trades") is True
        and production_qa.get("does_not_modify_strategy_action") is True
        and production_qa.get("does_not_modify_core_action") is True
        and production_qa.get("does_not_enter_evidence_effects") is True
        and production_qa.get("does_not_enter_next_session_projection") is True
        and acceptance.get("research_pass_is_not_trade_signal", True) is True
    )
    rows = [
        _factor_test_provider_validation_blocker_row(
            "storage_query_contract",
            "passed_local_read_contract" if storage_query_safe else "blocked_storage_query_boundary",
            storage_query_safe,
            f"storage_query_status={storage_query.get('status')}; metrics_from_storage={storage_query.get('metrics_computed_from_storage_query')}",
            "Keep storage rows as read-only sample metadata until an explicit research task constructs metric samples.",
            blockers=[] if storage_query_safe else ["storage_query_boundary_not_safe"],
        ),
        _factor_test_provider_validation_blocker_row(
            "local_dataset_sample_sufficiency",
            "passed_local_sufficiency" if local_dataset_sufficient else "blocked_or_missing_local_sample",
            local_dataset_sufficient,
            (
                f"status={local_dataset.get('status')}; "
                f"tickers={local_dataset.get('unique_factor_ticker_count')}; "
                f"dates={local_dataset.get('unique_factor_trade_date_count')}; "
                f"usable={local_dataset.get('usable_factor_value_count')}; "
                f"forward_returns={local_dataset.get('forward_return_sample_count')}"
            ),
            "Populate sufficient local factor_values and forward-return labels before real small-pool validation.",
            blockers=list(local_dataset.get("blocking_criteria") or []),
        ),
        _factor_test_provider_validation_blocker_row(
            "local_light_metrics_acceptance",
            "passed_local_light_metrics" if local_light_ready else "blocked_local_light_metrics",
            local_light_ready,
            f"small_pool_status={small_pool.get('status')}; local_light_observation_acceptance_done={local_light_ready}",
            "Keep IC / Rank IC / ICIR / group / cost / drawdown / neutral metrics passing on local light observations.",
            blockers=[] if local_light_ready else ["local_light_observation_acceptance"],
        ),
        _factor_test_provider_validation_blocker_row(
            "provider_backed_small_pool_sample",
            "passed_provider_sample" if provider_sample_done else "pending_provider_backed_sample",
            provider_sample_done,
            "provider-backed target sample validation is not executed by GET factor cache.",
            "Run a future explicit POST task with call_ledger, non-empty samples, and safe failure states.",
            blockers=[] if provider_sample_done else ["provider_backed_small_pool_sample"],
        ),
        _factor_test_provider_validation_blocker_row(
            "multi_window_research_validation",
            "passed_multi_window_validation" if not any(key in production_blocking_criteria for key in ("multi_horizon_forward_returns", "rolling_window_ic_icir", "out_of_sample_decay")) else "pending_multi_window_validation",
            not any(key in production_blocking_criteria for key in ("multi_horizon_forward_returns", "rolling_window_ic_icir", "out_of_sample_decay")),
            f"production_blocking_criteria={production_blocking_criteria}",
            "Validate multi-horizon returns, rolling IC/ICIR, sample split, and recent decay before promotion.",
            blockers=[key for key in production_blocking_criteria if key in {"multi_horizon_forward_returns", "rolling_window_ic_icir", "out_of_sample_decay"}],
        ),
        _factor_test_provider_validation_blocker_row(
            "cost_neutralization_bias_controls",
            "passed_cost_neutral_bias" if not any(key in production_blocking_criteria for key in ("transaction_cost_assumptions", "neutralization_stability", "pit_lookahead_survivorship_controls")) else "pending_cost_neutral_bias",
            not any(key in production_blocking_criteria for key in ("transaction_cost_assumptions", "neutralization_stability", "pit_lookahead_survivorship_controls")),
            f"production_blocking_criteria={production_blocking_criteria}",
            "Validate costs, neutralization stability, PIT/lookahead, and survivorship controls on target samples.",
            blockers=[key for key in production_blocking_criteria if key in {"transaction_cost_assumptions", "neutralization_stability", "pit_lookahead_survivorship_controls"}],
        ),
        _factor_test_provider_validation_blocker_row(
            "full_market_validation",
            "passed_full_market_validation" if full_market_done else "pending_full_market_validation",
            full_market_done,
            f"full_market_validation_done={full_market_done}",
            "Keep full-market validation pending until a separate worker-backed universe run proves it.",
            blockers=[] if full_market_done else ["full_market_validation"],
        ),
        _factor_test_provider_validation_blocker_row(
            "trade_action_isolation",
            "passed_trade_action_isolation" if trade_isolated else "blocked_trade_action_isolation",
            trade_isolated,
            "Factor Test rows remain research-only and do not enter action, evidence effects, or next-session projection.",
            "Preserve research-only isolation for every future validation stage.",
            blockers=[] if trade_isolated else ["trade_action_isolation"],
            production_blocker=not trade_isolated,
        ),
    ]
    production_blockers = [row for row in rows if row.get("production_blocker")]
    provider_validation_ready = not production_blockers
    return {
        "schema_version": "factor_test_provider_validation_blocker_audit.v1",
        "status": "provider_validation_blockers_visible" if production_blockers else "provider_validation_ready_for_promotion_review",
        "scope": "local_factor_test_provider_validation_blocker_audit_no_provider_execution",
        "created_at": now,
        "ltg": "LTG-03/LTG-11",
        "provider_validation_ready": provider_validation_ready,
        "provider_backed_small_pool_validation_done": provider_sample_done,
        "full_market_validation_done": full_market_done,
        "production_factor_test_validation_complete": False,
        "production_blocker_count": len(production_blockers),
        "production_blockers": [row["phase"] for row in production_blockers],
        "row_count": len(rows),
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "metrics_computed_from_local_dataset": False,
        "storage_query_rows_used_as_metrics": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_provider_validation_blocker_audit",
                "request_params_safe": {
                    "scope": "local_factor_test_provider_validation_blocker_audit_no_provider_execution",
                    "provider_backed_small_pool_validation_done": provider_sample_done,
                    "full_market_validation_done": full_market_done,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": local_dataset.get("latest_factor_trade_date"),
                "local_fetched_at": now,
                "call_status": "provider_validation_blockers_visible" if production_blockers else "provider_validation_ready_for_promotion_review",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This audit centralizes remaining Factor Test Lab provider-backed validation blockers. It does not call providers, compute production metrics, or promote trading actions.",
    }


def _attach_factor_test_provider_validation_blocker_audit(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    audit = _factor_test_provider_validation_blocker_audit(factor_tests, now)
    factor_tests["provider_validation_blocker_audit"] = audit
    factor_tests["provider_validation_blocker_rows"] = list(audit.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(audit.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["provider_validation_blocker_audit_ready"] = True
        acceptance["provider_validation_ready"] = bool(audit.get("provider_validation_ready"))
        acceptance["production_factor_test_validation_complete"] = False
        acceptance["provider_backed_small_pool_validation_done"] = bool(audit.get("provider_backed_small_pool_validation_done"))
        acceptance["full_market_validation_done"] = bool(audit.get("full_market_validation_done"))
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(audit.get("call_ledger") or [])


def _factor_test_provider_sample_readiness_receipt_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    *,
    required_before_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_promotion": bool(required_before_promotion),
        "evidence": evidence,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
    }


def _factor_test_provider_sample_readiness_receipt(factor_tests: dict[str, Any], now: str) -> dict[str, Any]:
    storage_query = factor_tests.get("storage_query_consumption") if isinstance(factor_tests.get("storage_query_consumption"), dict) else {}
    local_dataset = factor_tests.get("local_dataset_sample_evidence") if isinstance(factor_tests.get("local_dataset_sample_evidence"), dict) else {}
    small_pool = factor_tests.get("small_pool_acceptance") if isinstance(factor_tests.get("small_pool_acceptance"), dict) else {}
    production_qa = factor_tests.get("production_validation_qa_contract") if isinstance(factor_tests.get("production_validation_qa_contract"), dict) else {}
    provider_blocker = factor_tests.get("provider_validation_blocker_audit") if isinstance(factor_tests.get("provider_validation_blocker_audit"), dict) else {}

    storage_query_safe = bool(
        storage_query.get("schema_version") == "factor_test_storage_query_consumption.v1"
        and storage_query.get("metrics_computed_from_storage_query") is False
        and storage_query.get("storage_query_enters_strategy_action") is False
        and storage_query.get("writes_parquet_on_get") is False
        and storage_query.get("auto_refresh_on_get") is False
        and storage_query.get("external_calls_triggered") is False
    )
    local_dataset_sufficient = bool(local_dataset.get("local_dataset_sample_sufficiency_done"))
    local_light_ready = bool(small_pool.get("local_light_observation_acceptance_done"))
    production_qa_local_safe = bool(
        production_qa.get("schema_version") == "factor_test_production_validation_qa_contract.v1"
        and production_qa.get("scope") == "local_factor_test_validation_contract_not_provider_backed_execution"
        and production_qa.get("external_calls_triggered") is False
        and production_qa.get("provider_backed_small_pool_validation_done") is False
        and production_qa.get("production_factor_test_validation_complete") is False
    )
    blocker_audit_local_safe = bool(
        provider_blocker.get("schema_version") == "factor_test_provider_validation_blocker_audit.v1"
        and provider_blocker.get("scope") == "local_factor_test_provider_validation_blocker_audit_no_provider_execution"
        and provider_blocker.get("external_calls_triggered") is False
        and provider_blocker.get("production_factor_test_validation_complete") is False
    )
    provider_sample_done = bool(provider_blocker.get("provider_backed_small_pool_validation_done"))
    provider_validation_ready = bool(provider_blocker.get("provider_validation_ready"))
    production_blockers = [str(item) for item in provider_blocker.get("production_blockers", []) if item]
    production_blocker_count = int(provider_blocker.get("production_blocker_count") or len(production_blockers))
    missing_evidence_items = sorted(
        {
            *[str(item) for item in local_dataset.get("blocking_criteria", []) if item],
            *[str(item) for item in production_qa.get("blocking_criteria", []) if item],
            *production_blockers,
        }
    )
    ready_for_explicit_provider_small_pool_task = bool(
        storage_query_safe
        and local_dataset_sufficient
        and local_light_ready
        and production_qa_local_safe
        and blocker_audit_local_safe
        and not provider_sample_done
    )
    rows = [
        _factor_test_provider_sample_readiness_receipt_row(
            "button_gated_post_task_boundary",
            "passed_static_policy",
            True,
            "Provider-backed Factor Test samples may only run through an explicit POST task; GET cache and render stay read-only.",
            required_before_promotion=False,
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "storage_query_boundary_safe",
            "passed_local_read_contract" if storage_query_safe else "blocked_storage_query_boundary",
            storage_query_safe,
            f"storage_query_status={storage_query.get('status')}; metrics_from_storage={storage_query.get('metrics_computed_from_storage_query')}",
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "local_dataset_sample_sufficient",
            "passed_local_sufficiency" if local_dataset_sufficient else "blocked_local_sample_sufficiency",
            local_dataset_sufficient,
            (
                f"status={local_dataset.get('status')}; "
                f"tickers={local_dataset.get('unique_factor_ticker_count')}; "
                f"dates={local_dataset.get('unique_factor_trade_date_count')}; "
                f"usable={local_dataset.get('usable_factor_value_count')}; "
                f"forward_returns={local_dataset.get('forward_return_sample_count')}"
            ),
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "local_light_metrics_ready",
            "passed_local_light_metrics" if local_light_ready else "blocked_local_light_metrics",
            local_light_ready,
            f"small_pool_status={small_pool.get('status')}; local_light_observation_acceptance_done={local_light_ready}",
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "local_contracts_are_no_provider_call",
            "passed_no_provider_call" if production_qa_local_safe and blocker_audit_local_safe else "blocked_external_boundary",
            production_qa_local_safe and blocker_audit_local_safe,
            "Production QA and provider blocker audit are local/read-only contracts and cannot call Tushare, DeepSeek, or GitHub.",
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "provider_validation_blockers_visible",
            "passed_blockers_visible" if production_blocker_count > 0 or provider_validation_ready else "blocked_blocker_audit_missing",
            production_blocker_count > 0 or provider_validation_ready,
            f"provider_blocker_status={provider_blocker.get('status')}; production_blocker_count={production_blocker_count}",
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "provider_backed_sample_evidence_ticket",
            "ready_for_promotion_review" if provider_sample_done else "pending_provider_execution_evidence",
            provider_sample_done,
            "Provider-backed small-pool sample evidence is not created by GET factor cache.",
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "local_metrics_not_provider_acceptance",
            "enforced_not_provider_acceptance",
            True,
            "Light metrics, local dataset sufficiency, storage-query rows, QA rows, and blocker audits cannot be promoted by themselves.",
            required_before_promotion=False,
        ),
        _factor_test_provider_sample_readiness_receipt_row(
            "trade_and_action_boundary",
            "passed",
            True,
            "Receipt never executes trades, mutates action, enters evidence effects, or modifies next-session projection.",
            required_before_promotion=False,
        ),
    ]
    blocked_rows = [row["criterion"] for row in rows if row["required_before_promotion"] and not row["passed"]]
    allowed_next_step = (
        "review_prior_factor_test_provider_evidence"
        if provider_sample_done or provider_validation_ready
        else "explicit_post_task_factor_test_provider_small_pool_acceptance"
        if ready_for_explicit_provider_small_pool_task
        else "complete_local_dataset_sample_and_forward_returns"
    )
    return {
        "schema_version": "factor_test_provider_sample_readiness_receipt.v1",
        "status": "provider_small_pool_receipt_ready_for_promotion_review"
        if provider_sample_done or provider_validation_ready
        else "provider_small_pool_receipt_ready_execution_pending"
        if ready_for_explicit_provider_small_pool_task
        else "provider_small_pool_receipt_blocked_local_sample_or_contract",
        "scope": "local_factor_test_provider_sample_readiness_receipt_no_provider_execution",
        "created_at": now,
        "ltg": "LTG-03/LTG-11",
        "local_receipt_ready": True,
        "ready_for_explicit_provider_small_pool_task": ready_for_explicit_provider_small_pool_task,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache provider refresh",
            "React render provider refresh",
            "storage query rows as IC metrics",
            "local light metrics as provider acceptance",
            "blocker audit as production completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "storage_query_safe": storage_query_safe,
        "local_dataset_sample_sufficiency_done": local_dataset_sufficient,
        "local_light_observation_acceptance_done": local_light_ready,
        "provider_validation_ready": provider_validation_ready,
        "provider_backed_small_pool_validation_done": provider_sample_done,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "production_blocker_count": production_blocker_count,
        "production_blockers": production_blockers,
        "provider_refresh_called_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "row_count": len(rows),
        "blocked_readiness_count": len(blocked_rows),
        "blocked_readiness_items": blocked_rows,
        "missing_evidence_items": missing_evidence_items,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_provider_sample_readiness_receipt",
                "request_params_safe": {
                    "scope": "local_factor_test_provider_sample_readiness_receipt_no_provider_execution",
                    "ready_for_explicit_provider_small_pool_task": ready_for_explicit_provider_small_pool_task,
                    "provider_backed_small_pool_validation_done": provider_sample_done,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": local_dataset.get("latest_factor_trade_date"),
                "local_fetched_at": now,
                "call_status": allowed_next_step,
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This receipt summarizes the next safe LTG-03 provider-backed small-pool validation step. It never calls providers and cannot promote local metrics, storage rows, QA rows, or blocker audits to production validation.",
    }


def _attach_factor_test_provider_sample_readiness_receipt(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    receipt = _factor_test_provider_sample_readiness_receipt(factor_tests, now)
    factor_tests["provider_sample_readiness_receipt"] = receipt
    factor_tests["provider_sample_readiness_rows"] = list(receipt.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(receipt.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["provider_sample_readiness_receipt_ready"] = True
        acceptance["ready_for_explicit_provider_small_pool_task"] = bool(receipt.get("ready_for_explicit_provider_small_pool_task"))
        acceptance["provider_backed_small_pool_validation_done"] = bool(receipt.get("provider_backed_small_pool_validation_done"))
        acceptance["production_factor_test_validation_complete"] = False
        acceptance["full_market_validation_done"] = False
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(receipt.get("call_ledger") or [])


def _factor_test_provider_sample_activation_receipt_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    next_action: str,
    *,
    required_before_production: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_production": bool(required_before_production),
        "blocks_production_validation": bool(required_before_production and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "receipt_external_calls_triggered": False,
        "provider_task_created_by_receipt": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
    }


def _factor_test_provider_sample_activation_receipt(factor_tests: dict[str, Any], now: str) -> dict[str, Any]:
    readiness = factor_tests.get("provider_sample_readiness_receipt") if isinstance(factor_tests.get("provider_sample_readiness_receipt"), dict) else {}
    production_qa = factor_tests.get("production_validation_qa_contract") if isinstance(factor_tests.get("production_validation_qa_contract"), dict) else {}
    provider_blocker = factor_tests.get("provider_validation_blocker_audit") if isinstance(factor_tests.get("provider_validation_blocker_audit"), dict) else {}

    readiness_visible = bool(
        readiness.get("schema_version") == "factor_test_provider_sample_readiness_receipt.v1"
        and readiness.get("scope") == "local_factor_test_provider_sample_readiness_receipt_no_provider_execution"
        and readiness.get("cache_get_external_calls") is False
        and readiness.get("receipt_external_calls_triggered") is False
    )
    production_qa_visible = bool(
        production_qa.get("schema_version") == "factor_test_production_validation_qa_contract.v1"
        and production_qa.get("production_factor_test_validation_complete") is False
        and production_qa.get("external_calls_triggered") is False
    )
    blocker_visible = bool(
        provider_blocker.get("schema_version") == "factor_test_provider_validation_blocker_audit.v1"
        and provider_blocker.get("production_factor_test_validation_complete") is False
        and provider_blocker.get("external_calls_triggered") is False
    )
    ready_for_explicit_task = bool(readiness.get("ready_for_explicit_provider_small_pool_task"))
    provider_evidence_done = bool(readiness.get("provider_backed_small_pool_validation_done"))
    provider_validation_ready = bool(readiness.get("provider_validation_ready"))
    production_blocker_count = int(provider_blocker.get("production_blocker_count") or readiness.get("production_blocker_count") or 0)
    missing_evidence_items = sorted(
        {
            "explicit provider-backed small-pool task execution",
            "safe provider call ledger rows for target pool",
            "multi-horizon forward-return evidence",
            "rolling IC/Rank IC/ICIR evidence",
            "transaction cost and turnover assumptions evidence",
            "neutralization stability evidence",
            "PIT/lookahead/survivorship evidence",
            "explicit Factor Test production promotion marker",
            *[str(item) for item in readiness.get("missing_evidence_items", []) if item],
            *[str(item) for item in provider_blocker.get("production_blockers", []) if item],
        }
    )
    local_activation_ready = bool(readiness_visible and production_qa_visible and blocker_visible)
    allowed_next_step = (
        "review_prior_factor_test_provider_evidence"
        if provider_evidence_done or provider_validation_ready
        else "explicit_post_task_factor_test_provider_small_pool_acceptance"
        if ready_for_explicit_task
        else "complete_local_dataset_sample_and_forward_returns"
    )
    rows = [
        _factor_test_provider_sample_activation_receipt_row(
            "readiness_receipt_visible",
            "passed_local_receipt" if readiness_visible else "blocked_readiness_receipt_missing",
            readiness_visible,
            f"readiness_status={readiness.get('status')}; allowed_next_step={readiness.get('allowed_next_step')}",
            "Expose provider_sample_readiness_receipt before any explicit provider-backed small-pool task.",
            required_before_production=False,
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "explicit_post_task_required",
            "ready_for_explicit_post" if ready_for_explicit_task else "blocked_or_not_ready_for_provider_task",
            ready_for_explicit_task,
            "Provider-backed small-pool validation must be started only by a future explicit POST task.",
            "Complete local sample/forward-return evidence first when this row is blocked.",
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "provider_execution_evidence_required",
            "ready_for_promotion_review" if provider_evidence_done else "pending_provider_execution_evidence",
            provider_evidence_done,
            "This receipt does not execute providers or create call-ledger evidence.",
            "Run the explicit provider-backed acceptance task later and review safe call-ledger rows.",
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "production_qa_contract_visible",
            "passed_local_qa_contract" if production_qa_visible else "blocked_qa_contract_missing",
            production_qa_visible,
            f"production_qa_status={production_qa.get('status')}; pending={production_qa.get('pending_criterion_count')}",
            "Keep the production QA checklist visible until every production validation criterion is proven.",
            required_before_production=False,
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "provider_blocker_audit_visible",
            "passed_blockers_visible" if blocker_visible else "blocked_provider_blocker_missing",
            blocker_visible,
            f"provider_blocker_status={provider_blocker.get('status')}; blockers={production_blocker_count}",
            "Use blocker rows as missing-evidence ledger, not as provider-backed validation.",
            required_before_production=False,
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "local_metrics_not_acceptance",
            "enforced_not_provider_acceptance",
            True,
            "Local light metrics, local dataset sufficiency, storage-query rows, QA rows, and blocker rows cannot become provider-backed acceptance.",
            "Keep local metrics research-only until explicit provider evidence is present.",
            required_before_production=False,
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "cache_render_provider_boundary",
            "passed_no_provider_call",
            True,
            "GET factor cache and React render display this receipt only; they do not call providers or create tasks.",
            "Keep provider/model calls behind explicit POST/task modes.",
            required_before_production=False,
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "production_completion_boundary",
            "enforced_not_complete",
            False,
            "production_factor_test_validation_complete remains false until provider-backed small-pool, multi-window, cost, neutralization, bias, and promotion evidence are all present.",
            "Require a future explicit production promotion review before completion.",
        ),
        _factor_test_provider_sample_activation_receipt_row(
            "trade_and_action_boundary",
            "passed",
            True,
            "Activation receipt never executes trades, mutates strategy action, enters evidence effects, or changes next-session projection.",
            "Preserve Factor Test Lab as research-only.",
            required_before_production=False,
        ),
    ]
    blocked_rows = [row["criterion"] for row in rows if row["blocks_production_validation"]]
    return {
        "schema_version": "factor_test_provider_sample_activation_receipt.v1",
        "status": "provider_small_pool_activation_ready_execution_pending"
        if local_activation_ready and ready_for_explicit_task
        else "provider_small_pool_activation_ready_for_promotion_review"
        if local_activation_ready and (provider_evidence_done or provider_validation_ready)
        else "provider_small_pool_activation_blocked_local_sample_or_contract"
        if local_activation_ready
        else "provider_small_pool_activation_blocked_local_contract",
        "scope": "local_factor_test_provider_sample_activation_receipt_no_provider_execution",
        "created_at": now,
        "ltg": "LTG-03/LTG-11",
        "local_activation_receipt_ready": local_activation_ready,
        "ready_for_explicit_provider_small_pool_task": ready_for_explicit_task,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache provider refresh",
            "React render provider refresh",
            "activation receipt creates provider task",
            "storage query rows as IC metrics",
            "local light metrics as provider acceptance",
            "blocker audit as production completion",
            "activation receipt as production Factor Test completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": missing_evidence_items,
        "provider_backed_small_pool_validation_done": provider_evidence_done,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "provider_task_created_by_receipt": False,
        "provider_refresh_called_by_receipt": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "production_blocker_count": production_blocker_count,
        "blocking_criterion_count": len(blocked_rows),
        "blocking_criteria": blocked_rows,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_provider_sample_activation_receipt",
                "request_params_safe": {
                    "scope": "local_factor_test_provider_sample_activation_receipt_no_provider_execution",
                    "ready_for_explicit_provider_small_pool_task": ready_for_explicit_task,
                    "provider_backed_small_pool_validation_done": provider_evidence_done,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": now,
                "call_status": allowed_next_step,
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This activation receipt is a local LTG-03 checklist before future provider-backed small-pool validation. It does not call providers, create tasks, compute production metrics, execute trades, mutate action, or prove production Factor Test completion.",
    }


def _attach_factor_test_provider_sample_activation_receipt(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    receipt = _factor_test_provider_sample_activation_receipt(factor_tests, now)
    factor_tests["provider_sample_activation_receipt"] = receipt
    factor_tests["provider_sample_activation_rows"] = list(receipt.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(receipt.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["provider_sample_activation_receipt_ready"] = bool(receipt.get("local_activation_receipt_ready"))
        acceptance["provider_sample_activation_ready_for_explicit_task"] = bool(receipt.get("ready_for_explicit_provider_small_pool_task"))
        acceptance["provider_sample_activation_is_not_production_completion"] = True
        acceptance["provider_backed_small_pool_validation_done"] = bool(receipt.get("provider_backed_small_pool_validation_done"))
        acceptance["production_factor_test_validation_complete"] = False
        acceptance["full_market_validation_done"] = False
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(receipt.get("call_ledger") or [])


def _factor_test_clean_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    cleaned = "".join(char for char in text if char.isalnum() or char == ".")
    if len(cleaned) == 6 and cleaned[0] in {"0", "1", "2", "3"}:
        cleaned = f"{cleaned}.SZ"
    elif len(cleaned) == 6 and cleaned[0] in {"5", "6", "9"}:
        cleaned = f"{cleaned}.SH"
    if "." not in cleaned and len(cleaned) > 6:
        cleaned = cleaned[:6]
    return cleaned[:16]


def _factor_test_symbols_from_payload(payload: Any) -> tuple[list[str], list[str]]:
    if not isinstance(payload, dict):
        return [], []
    values: list[Any] = []
    for key in ("symbols", "ts_codes", "watchlist", "custom_pool", "universe"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            values.extend(candidate)
        elif isinstance(candidate, str):
            values.extend(part.strip() for part in candidate.replace(";", ",").split(","))
    for key in ("symbol", "ts_code", "ticker"):
        if payload.get(key):
            values.append(payload.get(key))
    symbols: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for value in values:
        symbol = _factor_test_clean_symbol(value)
        if not symbol:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        if len(symbols) >= FACTOR_TEST_PROVIDER_SMALL_POOL_SYMBOL_LIMIT:
            ignored.append(symbol)
            continue
        symbols.append(symbol)
    return symbols, ignored


def _factor_test_date(value: Any) -> _dt.date | None:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return _dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _factor_test_window(payload: Any, now: str) -> tuple[str, str, int]:
    now_date = _dt.datetime.fromisoformat(now).date()
    default_end = now_date
    default_start = default_end - _dt.timedelta(days=90)
    if isinstance(payload, dict):
        start = _factor_test_date(payload.get("start_date")) or default_start
        end = _factor_test_date(payload.get("end_date")) or default_end
    else:
        start = default_start
        end = default_end
    if start > end:
        start, end = end, start
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), (end - start).days + 1


def _factor_test_metrics_from_payload(payload: Any) -> tuple[list[str], list[str]]:
    if not isinstance(payload, dict):
        return list(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS), []
    raw_metrics = payload.get("metrics") or payload.get("requested_metrics") or []
    if isinstance(raw_metrics, str):
        raw_values = [part.strip() for part in raw_metrics.replace(";", ",").split(",")]
    elif isinstance(raw_metrics, list):
        raw_values = [str(item or "").strip() for item in raw_metrics]
    else:
        raw_values = []
    if not raw_values:
        return list(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS), []
    allowed = set(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS)
    selected: list[str] = []
    ignored: list[str] = []
    for item in raw_values:
        metric = item.lower().replace(" ", "_").replace("-", "_")
        if not metric:
            continue
        if metric in allowed and metric not in selected:
            selected.append(metric)
        elif metric not in allowed:
            ignored.append(metric[:40])
    return selected, ignored


def _factor_test_credential_presence() -> dict[str, Any]:
    token_present = any(key in os.environ for key in ("TUSHARE_TOKEN", "TUSHARE_API_TOKEN"))
    return {
        "schema_version": "factor_test_provider_small_pool_credential_presence.v1",
        "status": "credential_present" if token_present else "credential_missing",
        "server_side_tushare_credential_present": token_present,
        "safe_credential_label": "tushare_server_token",
        "credential_value_exposed": False,
        "env_key_name_exposed": False,
        "checked_by_membership_only": True,
    }


def _factor_test_scope_ticket(payload_safe: dict[str, Any]) -> dict[str, Any]:
    scope = {
        "symbols": payload_safe.get("symbols") or [],
        "start_date": payload_safe.get("start_date"),
        "end_date": payload_safe.get("end_date"),
        "window_days": payload_safe.get("window_days"),
        "metrics": payload_safe.get("metrics") or [],
        "horizons": payload_safe.get("forward_return_horizons") or [],
        "approved_by_user": payload_safe.get("approved_by_user") is True,
        "credential_present": _dict(payload_safe.get("credential_presence")).get("server_side_tushare_credential_present") is True,
        "symbol_limit": FACTOR_TEST_PROVIDER_SMALL_POOL_SYMBOL_LIMIT,
    }
    serialized = json.dumps(scope, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "schema_version": "factor_test_provider_small_pool_scope_ticket.v1",
        "scope_hash_algorithm": "sha256",
        "scope_hash": digest,
        "scope_hash_short": digest[:16],
        "scope_fields": scope,
        "contains_secret": False,
        "env_key_name_exposed": False,
        "credential_value_exposed": False,
    }


def _factor_test_provider_small_pool_dry_run_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    next_action: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_real_execution": bool(required),
        "blocks_real_execution": bool(required and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _factor_test_provider_small_pool_dry_run_payload(payload: Any, now: str) -> dict[str, Any]:
    symbols, ignored_symbols = _factor_test_symbols_from_payload(payload)
    start_date, end_date, window_days = _factor_test_window(payload, now)
    metrics, ignored_metrics = _factor_test_metrics_from_payload(payload)
    horizons_raw = []
    if isinstance(payload, dict):
        candidate = payload.get("forward_return_horizons") or payload.get("horizons") or ["1d", "5d"]
        if isinstance(candidate, str):
            horizons_raw = [part.strip() for part in candidate.replace(";", ",").split(",")]
        elif isinstance(candidate, list):
            horizons_raw = [str(item or "").strip() for item in candidate]
    if not horizons_raw:
        horizons_raw = ["1d", "5d"]
    horizons = []
    for horizon in horizons_raw:
        safe_horizon = "".join(char for char in horizon.lower() if char.isalnum())[:8]
        if safe_horizon and safe_horizon not in horizons:
            horizons.append(safe_horizon)
    approved_by_user = bool(isinstance(payload, dict) and payload.get("approved_by_user") is True)
    credential_presence = _factor_test_credential_presence()
    payload_safe: dict[str, Any] = {
        "approved_by_user": approved_by_user,
        "symbols": symbols,
        "ignored_symbols": ignored_symbols,
        "symbol_count": len(symbols),
        "symbol_limit": FACTOR_TEST_PROVIDER_SMALL_POOL_SYMBOL_LIMIT,
        "start_date": start_date,
        "end_date": end_date,
        "window_days": window_days,
        "minimum_symbol_count": FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS,
        "minimum_window_days": FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS,
        "metrics": metrics,
        "ignored_metrics": ignored_metrics,
        "required_metrics": list(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS),
        "forward_return_horizons": horizons,
        "required_datasets": list(FACTOR_TEST_PROVIDER_SMALL_POOL_ALLOWED_DATASETS),
        "credential_presence": credential_presence,
        "provider_execution_implemented": False,
        "provider_backed_small_pool_validation_done": False,
        "production_factor_test_validation_complete": False,
    }
    payload_safe["acceptance_scope_ticket"] = _factor_test_scope_ticket(payload_safe)
    return payload_safe


def _factor_test_provider_small_pool_dry_run_receipt(payload_safe: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    symbols = [str(item) for item in payload_safe.get("symbols", []) if item]
    metrics = [str(item) for item in payload_safe.get("metrics", []) if item]
    required_metrics = set(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS)
    selected_metric_set = set(metrics)
    missing_metrics = sorted(required_metrics - selected_metric_set)
    credential_presence = _dict(payload_safe.get("credential_presence"))
    credential_present = credential_presence.get("server_side_tushare_credential_present") is True
    approved_by_user = payload_safe.get("approved_by_user") is True
    window_days = int(payload_safe.get("window_days") or 0)
    rows = [
        _factor_test_provider_small_pool_dry_run_row(
            "explicit_user_approval",
            "passed_approved" if approved_by_user else "blocked_missing_approval",
            approved_by_user,
            f"approved_by_user={approved_by_user}",
            "User must explicitly approve the real provider-backed small-pool validation scope.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "symbol_scope_bounded",
            "passed_symbol_scope" if len(symbols) >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS else "blocked_not_enough_symbols",
            len(symbols) >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS,
            f"symbol_count={len(symbols)}; minimum={FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS}; limit={FACTOR_TEST_PROVIDER_SMALL_POOL_SYMBOL_LIMIT}",
            "Provide at least five bounded A-share symbols before real small-pool validation.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "window_scope_bounded",
            "passed_window_scope" if window_days >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS else "blocked_window_too_short",
            window_days >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS,
            f"window_days={window_days}; minimum={FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS}",
            "Use a long enough sample window before validating rolling IC, decay, and out-of-sample behavior.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "metric_scope_complete",
            "passed_metric_scope" if not missing_metrics else "blocked_missing_required_metrics",
            not missing_metrics,
            f"selected_metrics={metrics}; missing={missing_metrics}; ignored={payload_safe.get('ignored_metrics')}",
            "Keep IC, Rank IC, ICIR, group return, top-bottom, drawdown, neutral IC, decay, and cost model in the real acceptance scope.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "server_credential_presence_boolean_only",
            "passed_credential_present" if credential_present else "blocked_missing_server_credential",
            credential_present,
            f"credential_status={credential_presence.get('status')}; credential_value_exposed={credential_presence.get('credential_value_exposed')}",
            "Configure the server-side Tushare credential before a real provider-backed validation task.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "dataset_scope_visible",
            "passed_dataset_scope",
            True,
            f"required_datasets={payload_safe.get('required_datasets')}",
            "Real validation must refresh or read factor_values, daily, daily_basic, moneyflow, and trade_cal through audited task/storage paths.",
            required=False,
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "real_task_implementation_boundary",
            "pending_real_task_not_implemented",
            False,
            "This dry-run records a scope ticket only; it does not implement or execute the real provider-backed small-pool task.",
            "Implement a separate user-approved provider-backed validation task bound to this scope ticket.",
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "secret_redaction_boundary",
            "passed_no_secret_exposure",
            True,
            "Credential presence is reported as boolean/safe label only; raw values and env key names are not returned.",
            "Keep token/key values out of frontend, logs, packet, cache, and call_ledger.",
            required=False,
        ),
        _factor_test_provider_small_pool_dry_run_row(
            "trade_action_boundary",
            "passed_no_trade_or_action",
            True,
            "Dry-run cannot execute trades, mutate strategy action, enter evidence effects, or change next-session projection.",
            "Keep Factor Test Lab research-only.",
            required=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row["blocks_real_execution"]]
    preflight_ready = approved_by_user and len(symbols) >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_SYMBOLS and window_days >= FACTOR_TEST_PROVIDER_SMALL_POOL_MIN_WINDOW_DAYS and not missing_metrics and credential_present
    return {
        "schema_version": "factor_test_provider_small_pool_acceptance_dry_run.v1",
        "status": "provider_small_pool_dry_run_ready_real_execution_blocked" if preflight_ready else "provider_small_pool_dry_run_blocked_preflight",
        "scope": "local_factor_test_provider_small_pool_acceptance_dry_run_no_provider_execution",
        "created_at": now,
        "ltg": "LTG-03/LTG-11",
        "local_dry_run_ready": True,
        "preflight_ready_for_user_approved_real_task": preflight_ready,
        "ready_to_execute_real_task": False,
        "allowed_next_step": "implement_explicit_provider_small_pool_validation_task_bound_to_scope_ticket" if preflight_ready else "complete_provider_small_pool_preflight_scope",
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache provider refresh",
            "React render provider refresh",
            "dry-run as provider-backed small-pool validation",
            "local metrics as production Factor Test completion",
            "credential values or env key names in frontend/log/cache",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": [
            "real provider task implementation",
            "real Tushare/factor data call ledger",
            "multi-horizon forward-return rows",
            "rolling IC/Rank IC/ICIR evidence",
            "cost and turnover validation",
            "neutralization stability evidence",
            "PIT/lookahead/survivorship evidence",
            "production promotion review",
        ],
        "symbols": symbols,
        "symbol_count": len(symbols),
        "ignored_symbols": payload_safe.get("ignored_symbols") or [],
        "start_date": payload_safe.get("start_date"),
        "end_date": payload_safe.get("end_date"),
        "window_days": window_days,
        "metrics": metrics,
        "missing_metrics": missing_metrics,
        "ignored_metrics": payload_safe.get("ignored_metrics") or [],
        "forward_return_horizons": payload_safe.get("forward_return_horizons") or [],
        "credential_presence_summary": credential_presence,
        "acceptance_scope_ticket": payload_safe.get("acceptance_scope_ticket"),
        "acceptance_scope_hash": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash"),
        "acceptance_scope_hash_short": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash_short"),
        "provider_execution_implemented": False,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "contains_secret": False,
        "env_key_name_exposed": False,
        "credential_value_exposed": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blocking_criteria": blockers,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_provider_small_pool_acceptance_dry_run",
                "request_params_safe": {
                    "scope": "local_factor_test_provider_small_pool_acceptance_dry_run_no_provider_execution",
                    "symbol_count": len(symbols),
                    "window_days": window_days,
                    "metric_count": len(metrics),
                    "preflight_ready_for_user_approved_real_task": preflight_ready,
                    "acceptance_scope_hash_short": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash_short"),
                    "provider_execution_implemented": False,
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": payload_safe.get("end_date"),
                "local_fetched_at": now,
                "call_status": "local_dry_run_ready" if preflight_ready else "local_dry_run_blocked",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This is a local dry-run ticket for future LTG-03 provider-backed small-pool validation. It never calls providers/models, reads credential values, computes production metrics, executes trades, or mutates strategy action.",
    }, rows


def _factor_test_provider_small_pool_execution_recipe_row(
    phase_key: str,
    current_status: str,
    selected_by_scope: bool,
    evidence_required: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase_key": phase_key,
        "phase_label": FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASE_LABELS.get(phase_key, phase_key),
        "scope": "factor_test_provider_small_pool_execution_recipe",
        "current_status": current_status,
        "target_status": "provider_backed_small_pool_direct_evidence_required",
        "selected_by_dry_run_scope": bool(selected_by_scope),
        "required_before_production_factor_test_validation": True,
        "evidence_required": evidence_required,
        "next_action": next_action,
        "provider_task_created": False,
        "provider_execution_implemented": False,
        "provider_call_ledger_evidence_done": False,
        "sample_rows_collected": False,
        "multi_horizon_forward_returns_done": False,
        "rolling_window_validation_done": False,
        "cost_assumption_validation_done": False,
        "neutralization_stability_done": False,
        "pit_bias_controls_done": False,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "metrics_remain_research_only": True,
        "enters_strategy_action": False,
        "enters_core_action": False,
        "enters_evidence_effects": False,
        "enters_next_session_projection": False,
        "frontend_computes_action": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "env_key_name_exposed": False,
        "credential_value_exposed": False,
    }


def _factor_test_provider_small_pool_execution_recipe(factor_tests: dict[str, Any], now: str) -> dict[str, Any]:
    dry_run = factor_tests.get("provider_small_pool_acceptance_dry_run_receipt") if isinstance(factor_tests.get("provider_small_pool_acceptance_dry_run_receipt"), dict) else {}
    activation = factor_tests.get("provider_sample_activation_receipt") if isinstance(factor_tests.get("provider_sample_activation_receipt"), dict) else {}
    scope_ticket = _dict(dry_run.get("acceptance_scope_ticket"))
    scope_hash_short = str(dry_run.get("acceptance_scope_hash_short") or scope_ticket.get("scope_hash_short") or "")
    metrics = [str(item) for item in (dry_run.get("metrics") if isinstance(dry_run.get("metrics"), list) else []) if item]
    required_metric_set = set(FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS)
    scope_ticket_ready = bool(
        dry_run.get("schema_version") == "factor_test_provider_small_pool_acceptance_dry_run.v1"
        and dry_run.get("preflight_ready_for_user_approved_real_task") is True
        and scope_hash_short
        and required_metric_set <= set(metrics)
    )
    activation_ready = bool(activation.get("ready_for_explicit_provider_small_pool_task") is True)
    recipe_ready = scope_ticket_ready
    status = (
        "factor_test_provider_small_pool_execution_recipe_ready_execution_pending"
        if recipe_ready
        else "factor_test_provider_small_pool_execution_recipe_blocked_scope_or_preflight"
    )
    phase_status = {
        "scope_ticket_review": "ready_scope_ticket_visible" if scope_ticket_ready else "blocked_missing_provider_small_pool_scope_ticket",
        "explicit_provider_task_creation": "pending_explicit_post_provider_small_pool_validation",
        "provider_call_ledger_capture": "pending_safe_provider_call_ledger",
        "sample_row_collection": "pending_non_empty_provider_sample_rows",
        "multi_horizon_forward_returns": "pending_multi_horizon_forward_return_labels",
        "rolling_ic_icir_validation": "pending_rolling_ic_icir_validation",
        "cost_turnover_validation": "pending_cost_turnover_validation",
        "neutralization_stability_validation": "pending_neutralization_stability_validation",
        "pit_bias_controls_validation": "pending_pit_lookahead_survivorship_controls",
        "promotion_review": "blocked_until_provider_evidence_review_passes",
    }
    evidence_by_phase = {
        "scope_ticket_review": "approved provider small-pool dry-run scope ticket",
        "explicit_provider_task_creation": "explicit provider task_id bound to scope hash",
        "provider_call_ledger_capture": "safe provider call ledger rows for target pool",
        "sample_row_collection": "non-empty provider-backed sample rows",
        "multi_horizon_forward_returns": "multi-horizon forward-return labels",
        "rolling_ic_icir_validation": "rolling IC/Rank IC/ICIR evidence",
        "cost_turnover_validation": "cost and turnover assumption evidence",
        "neutralization_stability_validation": "industry and market-cap neutralization stability evidence",
        "pit_bias_controls_validation": "PIT, lookahead, and survivorship controls evidence",
        "promotion_review": "manual Factor Test production promotion review",
    }
    rows = [
        _factor_test_provider_small_pool_execution_recipe_row(
            phase_key,
            phase_status[phase_key],
            recipe_ready,
            evidence_by_phase[phase_key],
            "Run this phase only through a future explicit provider-backed validation task; never from GET cache or React render.",
        )
        for phase_key in FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES
    ]
    return {
        "schema_version": "factor_test_provider_small_pool_execution_recipe.v1",
        "status": status,
        "scope": "local_factor_test_provider_small_pool_execution_recipe_no_provider_execution",
        "created_at": now,
        "ltg": "LTG-03/LTG-11/LTG-12",
        "local_recipe_ready": recipe_ready,
        "execution_recipe_ready": recipe_ready,
        "scope_ticket_ready": scope_ticket_ready,
        "activation_ready_for_provider_task": activation_ready,
        "acceptance_scope_hash_short": scope_hash_short,
        "symbol_count": int(dry_run.get("symbol_count") or 0),
        "window_days": int(dry_run.get("window_days") or 0),
        "phase_keys": list(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
        "pending_phases": list(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
        "phase_count": len(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
        "pending_phase_count": len(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
        "allowed_execution_sequence": list(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
        "required_evidence": [
            "approved provider small-pool dry-run scope ticket",
            "explicit provider task_id bound to scope hash",
            "safe provider call ledger rows for target pool",
            "non-empty provider-backed sample rows",
            "multi-horizon forward-return labels",
            "rolling IC/Rank IC/ICIR evidence",
            "cost and turnover assumption evidence",
            "industry and market-cap neutralization stability evidence",
            "PIT, lookahead, and survivorship controls evidence",
            "manual Factor Test production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_recipe_as_provider_execution_evidence",
            "create provider task from GET cache",
            "call Tushare from this recipe",
            "call DeepSeek from this recipe",
            "call GitHub from this recipe",
            "compute production IC from React",
            "local metrics as provider acceptance",
            "mutate strategy action",
            "real trade execution",
            "mark production Factor Test complete from recipe",
        ],
        "provider_task_created": False,
        "provider_execution_implemented": False,
        "provider_refresh_called": False,
        "provider_call_ledger_evidence_done": False,
        "sample_rows_collected": False,
        "multi_horizon_forward_returns_done": False,
        "rolling_window_validation_done": False,
        "cost_assumption_validation_done": False,
        "neutralization_stability_done": False,
        "pit_bias_controls_done": False,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "metrics_remain_research_only": True,
        "enters_strategy_action": False,
        "enters_core_action": False,
        "enters_evidence_effects": False,
        "enters_next_session_projection": False,
        "frontend_computes_action": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "env_key_name_exposed": False,
        "credential_value_exposed": False,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_test_provider_small_pool_execution_recipe",
                "request_params_safe": {
                    "scope": "local_factor_test_provider_small_pool_execution_recipe_no_provider_execution",
                    "scope_ticket_ready": scope_ticket_ready,
                    "activation_ready_for_provider_task": activation_ready,
                    "execution_recipe_ready": recipe_ready,
                    "acceptance_scope_hash_short": scope_hash_short,
                    "phase_count": len(FACTOR_TEST_PROVIDER_SMALL_POOL_EXECUTION_PHASES),
                    "production_factor_test_validation_complete": False,
                },
                "row_count": len(rows),
                "data_date": dry_run.get("end_date"),
                "local_fetched_at": now,
                "call_status": "local_recipe_ready_execution_pending" if recipe_ready else "local_recipe_blocked_scope_or_preflight",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This local recipe fixes the future provider-backed Factor Test small-pool validation order. It does not create tasks, call Tushare/DeepSeek/GitHub, compute production metrics, execute trades, or mutate strategy action.",
    }


def _attach_factor_test_provider_small_pool_execution_recipe(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    factor_tests = packet.get("factor_tests") if isinstance(packet.get("factor_tests"), dict) else {}
    factor_tests = dict(factor_tests)
    recipe = _factor_test_provider_small_pool_execution_recipe(factor_tests, now)
    factor_tests["provider_small_pool_execution_recipe"] = recipe
    factor_tests["provider_small_pool_execution_rows"] = list(recipe.get("rows") or [])
    existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
    factor_tests["call_ledger"] = list(existing_test_ledger) + list(recipe.get("call_ledger") or [])
    acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
    if acceptance:
        acceptance = dict(acceptance)
        acceptance["provider_small_pool_execution_recipe_ready"] = bool(recipe.get("local_recipe_ready"))
        acceptance["provider_small_pool_execution_recipe_status"] = recipe.get("status")
        acceptance["provider_small_pool_execution_recipe_is_not_provider_execution"] = True
        acceptance["provider_execution_implemented"] = False
        acceptance["provider_backed_small_pool_validation_done"] = False
        acceptance["production_factor_test_validation_complete"] = False
        acceptance["full_market_validation_done"] = False
        factor_tests["acceptance_contract"] = acceptance
    packet["factor_tests"] = factor_tests
    return packet, list(recipe.get("call_ledger") or [])


def run_factor_test_provider_small_pool_acceptance_dry_run_task(payload: Any = None) -> dict[str, Any]:
    now = _now_iso()
    payload_safe = _factor_test_provider_small_pool_dry_run_payload(payload, now)
    receipt, rows = _factor_test_provider_small_pool_dry_run_receipt(payload_safe, now)
    payload_safe["provider_small_pool_acceptance_dry_run_receipt"] = receipt
    payload_safe["provider_small_pool_acceptance_dry_run_rows"] = rows
    task = create_task_record(
        "run_factor_test_provider_small_pool_acceptance_dry_run",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload_safe,
        current_step="factor_test_provider_small_pool_dry_run_queued",
        warnings=[
            "Factor Test provider 小股票池 dry-run 只生成本地 scope ticket，不调用 Tushare、DeepSeek 或 GitHub。",
            "dry-run 不计算生产 IC / Rank IC / ICIR，不修改 strategy action，不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="building_factor_test_provider_small_pool_scope_ticket")
    try:
        hub = dict(read_factor_quant_cache())
        factor_tests = hub.get("factor_tests") if isinstance(hub.get("factor_tests"), dict) else {}
        factor_tests = dict(factor_tests)
        factor_tests["provider_small_pool_acceptance_dry_run_receipt"] = receipt
        factor_tests["provider_small_pool_acceptance_dry_run_rows"] = rows
        acceptance = factor_tests.get("acceptance_contract") if isinstance(factor_tests.get("acceptance_contract"), dict) else {}
        if acceptance:
            acceptance = dict(acceptance)
            acceptance["provider_small_pool_acceptance_dry_run_ready"] = bool(receipt.get("local_dry_run_ready"))
            acceptance["provider_small_pool_acceptance_scope_ticket_ready"] = bool(receipt.get("acceptance_scope_hash_short"))
            acceptance["provider_small_pool_dry_run_is_not_provider_execution"] = True
            acceptance["provider_backed_small_pool_validation_done"] = False
            acceptance["production_factor_test_validation_complete"] = False
            factor_tests["acceptance_contract"] = acceptance
        existing_test_ledger = factor_tests.get("call_ledger") if isinstance(factor_tests.get("call_ledger"), list) else []
        factor_tests["call_ledger"] = list(receipt.get("call_ledger") or []) + list(existing_test_ledger)
        hub["factor_tests"] = factor_tests
        hub["call_ledger"] = list(receipt.get("call_ledger") or []) + list(hub.get("call_ledger") if isinstance(hub.get("call_ledger"), list) else [])
        warning = "Factor Test provider 小股票池 dry-run ticket 已生成：本地 preflight，不调用 provider，不代表生产验收完成。"
        existing_warnings = hub.get("warnings") if isinstance(hub.get("warnings"), list) else []
        hub["warnings"] = [warning] + [item for item in existing_warnings if item != warning]
        hub["external_calls_triggered"] = False
        hub["tushare_called"] = False
        hub["deepseek_called"] = False
        hub["github_called"] = False
        hub["does_not_execute_trades"] = True
        hub["does_not_modify_strategy_action"] = True
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
    except Exception as exc:
        payload_safe["cache_write_error_safe"] = str(exc).splitlines()[0][:240]
    updated = update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(receipt.get("status") or "factor_test_provider_small_pool_dry_run_ready"),
        call_ledger=list(receipt.get("call_ledger") or []),
    ) or task
    updated["payload_safe"] = payload_safe
    return updated


def _factor_universe_mode_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "watchlist"
    mode = str(payload.get("universe_mode") or payload.get("mode") or "watchlist")
    if mode in FACTOR_UNIVERSE_RESEARCH_PLAN_MODES:
        return mode
    return "watchlist"


def _factor_universe_items_from_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    values: list[Any] = []
    for key in ("universe", "items", "ts_codes", "symbols", "watchlist", "custom_pool"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            values.extend(candidate)
        elif isinstance(candidate, str) and candidate.strip():
            values.extend(part.strip() for part in candidate.replace(";", ",").split(","))
    items: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        if any(marker in text.lower() for marker in FACTOR_UNIVERSE_ITEM_SECRET_MARKERS):
            continue
        seen.add(text)
        items.append(text[:32])
    return items[:100]


def _factor_universe_task_payload_summary(payload: Any) -> dict[str, Any]:
    mode = _factor_universe_mode_from_payload(payload)
    items = _factor_universe_items_from_payload(payload)
    return {
        "universe_mode": mode,
        "universe_size": len(items),
        "universe_items": items[:20],
        "external_sources_allowed": False,
        "full_pool_validation_requested": mode == "full_pool",
        "full_pool_validation_done": False,
    }


def _factor_universe_storage_packet(dataset: str, *, limit: int) -> dict[str, Any]:
    if dataset == "factor_values":
        return storage_service.factor_values_status(limit=limit)
    return storage_service.parquet_dataset_status(dataset, limit=limit)


def _factor_universe_storage_read_rows(*, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in FACTOR_UNIVERSE_RESEARCH_PLAN_DATASETS:
        packet = _factor_universe_storage_packet(dataset, limit=limit)
        contract = packet.get("query_result_contract") if isinstance(packet.get("query_result_contract"), dict) else {}
        page_info = packet.get("page_info") if isinstance(packet.get("page_info"), dict) else {}
        metadata = packet.get("metadata") if isinstance(packet.get("metadata"), dict) else {}
        query = packet.get("query") if isinstance(packet.get("query"), dict) else {}
        projected_columns = packet.get("projected_columns") if isinstance(packet.get("projected_columns"), list) else []
        missing_projected_columns = packet.get("missing_projected_columns") if isinstance(packet.get("missing_projected_columns"), list) else []
        returned_row_count = int(page_info.get("returned_row_count") or packet.get("row_count") or 0)
        rows.append(
            {
                "dataset": dataset,
                "source_endpoint": "GET /api/storage/factor-values" if dataset == "factor_values" else f"GET /api/storage/{dataset}",
                "storage_status": packet.get("status") or metadata.get("status") or "missing",
                "query_status": contract.get("status") or query.get("status") or packet.get("status") or "missing",
                "query_wrapper": packet.get("query_wrapper") or query.get("query_wrapper") or "duckdb_filtered_parquet.v1",
                "query_result_contract_schema_version": contract.get("schema_version") or "duckdb_query_result_contract.v1",
                "query_result_contract_consumed": bool(contract),
                "cursor_pagination_consumed": bool(page_info),
                "projected_columns": projected_columns,
                "missing_projected_columns": missing_projected_columns,
                "returned_row_count": returned_row_count,
                "storage_row_count": int(packet.get("row_count") or 0),
                "next_cursor": page_info.get("next_cursor") or "",
                "sample_row_limit": limit,
                "row_payload_exposed_to_factor_research": False,
                "metrics_computed_from_storage_query": False,
                "full_pool_validation_done": False,
                "large_universe_pipeline_done": False,
                "cache_get_writes_files": False,
                "writes_parquet_on_get": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _build_factor_universe_research_read_plan(payload: Any, now: str) -> dict[str, Any]:
    mode = _factor_universe_mode_from_payload(payload)
    items = _factor_universe_items_from_payload(payload)
    rows = _factor_universe_storage_read_rows(limit=5)
    missing_contract_count = sum(1 for row in rows if not row["query_result_contract_consumed"])
    missing_dataset_count = sum(1 for row in rows if str(row.get("storage_status") or "") == "missing")
    return {
        "schema_version": "factor_universe_research_read_plan.v1",
        "status": "read_plan_ready",
        "task_type": "run_factor_universe_research_plan",
        "created_at": now,
        "requested_universe_mode": mode,
        "universe_items": items[:50],
        "universe_size": len(items),
        "dataset_count": len(rows),
        "storage_query_contract_count": len(rows) - missing_contract_count,
        "missing_query_contract_count": missing_contract_count,
        "missing_dataset_count": missing_dataset_count,
        "storage_query_rows": rows,
        "worker_task_consumption_plan_ready": True,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "watchlist_pipeline_done": False,
        "custom_pool_pipeline_done": False,
        "metrics_computed": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "page_render_starts_full_pool": False,
        "frontend_computes_rank_zscore": False,
        "partial_pool_is_full_market_proof": False,
        "cache_only_storage_contracts": True,
        "post_task_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Factor universe 读取计划只消费本地 storage 查询合同；不跑 full-pool 研究、不计算交易动作。",
    }


def _factor_universe_read_plan_call_ledger(plan: dict[str, Any], now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_factor_universe_research_read_plan",
            "request_params_safe": {
                "universe_mode": plan.get("requested_universe_mode"),
                "universe_size": plan.get("universe_size"),
                "dataset_count": plan.get("dataset_count"),
                "storage_query_contract_count": plan.get("storage_query_contract_count"),
                "full_pool_validation_done": False,
            },
            "row_count": int(plan.get("dataset_count") or 0),
            "data_date": None,
            "local_fetched_at": now,
            "call_status": str(plan.get("status") or "read_plan_ready"),
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _factor_universe_worker_batch_items_from_payload(payload: Any) -> tuple[list[str], list[str]]:
    if not isinstance(payload, dict):
        return [], []
    values: list[Any] = []
    for key in ("universe", "items", "ts_codes", "symbols", "watchlist", "custom_pool"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            values.extend(candidate)
        elif isinstance(candidate, str) and candidate.strip():
            values.extend(part.strip() for part in candidate.replace(";", ",").split(","))
    items: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        if any(marker in text.lower() for marker in FACTOR_UNIVERSE_ITEM_SECRET_MARKERS):
            if "secret_like_item_redacted" not in ignored:
                ignored.append("secret_like_item_redacted")
            continue
        safe_text = text[:32]
        if safe_text in seen:
            continue
        seen.add(safe_text)
        if len(items) >= FACTOR_UNIVERSE_WORKER_BATCH_SYMBOL_LIMIT:
            ignored.append("symbol_limit_exceeded")
            continue
        items.append(safe_text)
    return items, ignored[:20]


def _factor_universe_worker_batch_requested_stages(payload: Any) -> tuple[list[str], list[str], list[str]]:
    raw: list[Any] = []
    if isinstance(payload, dict):
        candidate = payload.get("requested_stages") or payload.get("stages") or payload.get("stage_scope")
        if isinstance(candidate, str):
            raw = [part.strip() for part in candidate.replace(";", ",").split(",")]
        elif isinstance(candidate, list):
            raw = candidate
    if not raw:
        raw = list(FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)
    allowed = set(FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)
    stages: list[str] = []
    ignored: list[str] = []
    for item in raw:
        text = "".join(char if char.isalnum() else "_" for char in str(item or "").strip().lower()).strip("_")[:48]
        if not text:
            continue
        if text not in allowed:
            if text not in ignored:
                ignored.append(text)
            continue
        if text not in stages:
            stages.append(text)
    missing = [stage for stage in FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES if stage not in stages]
    return stages, missing, ignored[:20]


def _factor_universe_worker_batch_scope_ticket(payload_safe: dict[str, Any]) -> dict[str, Any]:
    scope = {
        "universe_mode": payload_safe.get("universe_mode"),
        "symbol_count": payload_safe.get("symbol_count"),
        "symbols": payload_safe.get("symbols"),
        "required_datasets": payload_safe.get("required_datasets"),
        "requested_stages": payload_safe.get("requested_stages"),
        "required_stages": payload_safe.get("required_stages"),
        "worker_backend": "future_celery_or_local_worker_batch",
        "production_flags": {
            "worker_execution_implemented": False,
            "large_universe_pipeline_done": False,
            "cross_sectional_rank_zscore_done": False,
            "neutralization_done": False,
            "factor_combination_research_done": False,
            "production_factor_universe_complete": False,
        },
    }
    digest = hashlib.sha256(json.dumps(scope, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "schema_version": "factor_universe_worker_batch_scope_ticket.v1",
        "scope_hash_algorithm": "sha256",
        "scope_hash": digest,
        "scope_hash_short": digest[:16],
        "contains_secret": False,
        "credential_value_exposed": False,
        "env_key_name_exposed": False,
        "scope": scope,
    }


def _factor_universe_worker_batch_dry_run_row(
    criterion: str,
    status: str,
    passed: bool,
    evidence: str,
    next_action: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_for_real_worker_execution": required,
        "blocks_worker_execution": required and not passed,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _factor_universe_worker_batch_dry_run_payload(payload: Any, now: str) -> dict[str, Any]:
    mode = _factor_universe_mode_from_payload(payload)
    symbols, ignored_symbols = _factor_universe_worker_batch_items_from_payload(payload)
    stages, missing_stages, ignored_stages = _factor_universe_worker_batch_requested_stages(payload)
    approved_by_user = bool(isinstance(payload, dict) and payload.get("approved_by_user") is True)
    payload_safe: dict[str, Any] = {
        "approved_by_user": approved_by_user,
        "universe_mode": mode,
        "symbols": symbols,
        "ignored_symbols": ignored_symbols,
        "symbol_count": len(symbols),
        "symbol_limit": FACTOR_UNIVERSE_WORKER_BATCH_SYMBOL_LIMIT,
        "minimum_symbol_count_for_watchlist_or_custom_pool": FACTOR_UNIVERSE_WORKER_BATCH_MIN_SYMBOLS,
        "full_pool_uses_server_side_universe_resolver": mode == "full_pool",
        "required_datasets": list(FACTOR_UNIVERSE_RESEARCH_PLAN_DATASETS),
        "required_stages": list(FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES),
        "requested_stages": stages,
        "missing_required_stages": missing_stages,
        "ignored_stages": ignored_stages,
        "created_at": now,
        "worker_batch_requires_explicit_post_task": True,
        "worker_execution_implemented": False,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "production_factor_universe_complete": False,
    }
    payload_safe["worker_batch_scope_ticket"] = _factor_universe_worker_batch_scope_ticket(payload_safe)
    return payload_safe


def _factor_universe_worker_batch_dry_run_receipt(payload_safe: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mode = str(payload_safe.get("universe_mode") or "watchlist")
    symbol_count = int(payload_safe.get("symbol_count") or 0)
    approved_by_user = payload_safe.get("approved_by_user") is True
    missing_stages = [str(item) for item in payload_safe.get("missing_required_stages") or []]
    full_pool_scope = mode == "full_pool"
    bounded_scope = full_pool_scope or symbol_count >= FACTOR_UNIVERSE_WORKER_BATCH_MIN_SYMBOLS
    read_plan = _build_factor_universe_research_read_plan(
        {"universe_mode": mode, "symbols": payload_safe.get("symbols") or []},
        now,
    )
    read_plan_ready = read_plan.get("status") == "read_plan_ready"
    preflight_ready = approved_by_user and bounded_scope and not missing_stages and read_plan_ready
    rows = [
        _factor_universe_worker_batch_dry_run_row(
            "explicit_user_approval",
            "passed_approved" if approved_by_user else "blocked_missing_approval",
            approved_by_user,
            f"approved_by_user={approved_by_user}",
            "User must explicitly approve the future worker-batch research scope.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "universe_scope_bounded",
            "passed_full_pool_scope" if full_pool_scope else "passed_symbol_scope" if bounded_scope else "blocked_not_enough_symbols",
            bounded_scope,
            f"universe_mode={mode}; symbol_count={symbol_count}; minimum={FACTOR_UNIVERSE_WORKER_BATCH_MIN_SYMBOLS}; limit={FACTOR_UNIVERSE_WORKER_BATCH_SYMBOL_LIMIT}",
            "Use full_pool with a server-side resolver or provide a bounded watchlist/custom_pool before worker execution.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "required_stages_complete",
            "passed_stage_scope" if not missing_stages else "blocked_missing_required_stages",
            not missing_stages,
            f"requested_stages={payload_safe.get('requested_stages')}; missing={missing_stages}; ignored={payload_safe.get('ignored_stages')}",
            "Keep storage read plan, worker batch, rank, zscore, neutralization, combination, summary, and promotion review in scope.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "storage_read_plan_visible",
            "passed_read_plan_ready" if read_plan_ready else "blocked_read_plan_missing",
            read_plan_ready,
            f"read_plan_status={read_plan.get('status')}; dataset_count={read_plan.get('dataset_count')}; storage_query_contract_count={read_plan.get('storage_query_contract_count')}",
            "Generate and keep a local storage read plan before worker-batch execution.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "worker_execution_implementation_boundary",
            "pending_worker_execution_not_implemented",
            False,
            "This dry-run creates a scope ticket only; it does not start Celery/local workers or execute batch research.",
            "Implement a separate explicit worker-batch task bound to this scope ticket.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "rank_zscore_neutralization_boundary",
            "pending_production_metrics_not_computed",
            False,
            "No production rank, zscore, neutralization, factor combination, out-of-sample, or full-pool metrics are computed by this ticket.",
            "Run the future worker-backed research task and attach audited research metrics before promotion review.",
        ),
        _factor_universe_worker_batch_dry_run_row(
            "frontend_boundary",
            "passed_frontend_display_only",
            True,
            "React only posts the gated task and renders cache receipts; it does not compute universe research.",
            "Keep heavy universe research out of React render paths.",
            required=False,
        ),
        _factor_universe_worker_batch_dry_run_row(
            "external_call_boundary",
            "passed_no_external_call",
            True,
            "Dry-run reads local storage contracts only and does not call Tushare, DeepSeek, GitHub, or browser APIs.",
            "Only future explicit provider/model tasks may call external services under mode gates.",
            required=False,
        ),
        _factor_universe_worker_batch_dry_run_row(
            "trade_action_boundary",
            "passed_no_trade_or_action",
            True,
            "Dry-run cannot execute trades, mutate strategy action, change price/position, or write operation zones.",
            "Keep universe research outputs research-only until a separate promotion review.",
            required=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row["blocks_worker_execution"]]
    return {
        "schema_version": "factor_universe_worker_batch_dry_run.v1",
        "status": "worker_batch_dry_run_ready_real_execution_blocked" if preflight_ready else "worker_batch_dry_run_blocked_preflight",
        "scope": "local_factor_universe_worker_batch_dry_run_no_worker_or_provider_execution",
        "created_at": now,
        "ltg": "LTG-04/LTG-11",
        "local_dry_run_ready": True,
        "preflight_ready_for_explicit_worker_batch_task": preflight_ready,
        "ready_to_execute_worker_task": False,
        "allowed_next_step": "implement_explicit_factor_universe_worker_batch_task_bound_to_scope_ticket" if preflight_ready else "complete_factor_universe_worker_batch_preflight_scope",
        "not_allowed_next_steps": [
            "GET /api/factor-quant/cache worker batch execution",
            "React render full-pool execution",
            "worker-batch dry-run as production Factor universe completion",
            "local rank/zscore preview as production research",
            "Tushare or DeepSeek call from this dry-run",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": [
            "explicit worker task implementation",
            "worker execution task_id and durable task logs",
            "large-universe batch result rows",
            "cross-sectional rank/zscore evidence",
            "industry and market-cap neutralization evidence",
            "factor combination research evidence",
            "out-of-sample and decay evidence",
            "production promotion review",
        ],
        "universe_mode": mode,
        "symbols": payload_safe.get("symbols") or [],
        "symbol_count": symbol_count,
        "ignored_symbols": payload_safe.get("ignored_symbols") or [],
        "symbol_limit": FACTOR_UNIVERSE_WORKER_BATCH_SYMBOL_LIMIT,
        "minimum_symbol_count_for_watchlist_or_custom_pool": FACTOR_UNIVERSE_WORKER_BATCH_MIN_SYMBOLS,
        "full_pool_uses_server_side_universe_resolver": full_pool_scope,
        "required_datasets": payload_safe.get("required_datasets") or [],
        "required_stages": payload_safe.get("required_stages") or [],
        "requested_stages": payload_safe.get("requested_stages") or [],
        "missing_required_stages": missing_stages,
        "ignored_stages": payload_safe.get("ignored_stages") or [],
        "storage_read_plan_status": read_plan.get("status"),
        "storage_read_plan_dataset_count": read_plan.get("dataset_count"),
        "storage_query_contract_count": read_plan.get("storage_query_contract_count"),
        "worker_batch_scope_ticket": payload_safe.get("worker_batch_scope_ticket"),
        "worker_batch_scope_hash": _dict(payload_safe.get("worker_batch_scope_ticket")).get("scope_hash"),
        "worker_batch_scope_hash_short": _dict(payload_safe.get("worker_batch_scope_ticket")).get("scope_hash_short"),
        "worker_execution_implemented": False,
        "worker_batch_executed": False,
        "large_universe_pipeline_done": False,
        "watchlist_pipeline_done": False,
        "custom_pool_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "production_factor_universe_complete": False,
        "partial_pool_is_full_market_proof": False,
        "page_render_starts_full_pool": False,
        "frontend_computes_rank_zscore": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_core_action": True,
        "does_not_enter_evidence_effects": True,
        "does_not_enter_next_session_projection": True,
        "contains_secret": False,
        "credential_value_exposed": False,
        "env_key_name_exposed": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blocking_criteria": blockers,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_universe_worker_batch_dry_run",
                "request_params_safe": {
                    "scope": "local_factor_universe_worker_batch_dry_run_no_worker_or_provider_execution",
                    "universe_mode": mode,
                    "symbol_count": symbol_count,
                    "required_stage_count": len(FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES),
                    "preflight_ready_for_explicit_worker_batch_task": preflight_ready,
                    "worker_batch_scope_hash_short": _dict(payload_safe.get("worker_batch_scope_ticket")).get("scope_hash_short"),
                    "worker_execution_implemented": False,
                    "production_factor_universe_complete": False,
                },
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": now,
                "call_status": "local_dry_run_ready" if preflight_ready else "local_dry_run_blocked",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This is a local dry-run ticket for future LTG-04 worker-backed universe research. It does not start workers, call providers/models, compute production metrics, execute trades, or mutate strategy action.",
    }, rows


def _factor_universe_worker_batch_execution_recipe_row(
    phase_key: str,
    current_status: str,
    selected_by_scope: bool,
    evidence_required: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase_key": phase_key,
        "phase_label": FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASE_LABELS.get(phase_key, phase_key),
        "scope": "factor_universe_worker_batch_execution_recipe",
        "current_status": current_status,
        "target_status": "worker_backed_batch_research_evidence_required",
        "selected_by_worker_dry_run_scope": bool(selected_by_scope),
        "required_before_production": True,
        "evidence_required": evidence_required,
        "next_action": next_action,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "storage_read_executed": False,
        "large_universe_pipeline_done": False,
        "cross_sectional_rank_zscore_done": False,
        "zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "result_summary_persisted": False,
        "full_pool_validation_done": False,
        "production_factor_universe_complete": False,
        "page_render_starts_full_pool": False,
        "frontend_computes_rank_zscore": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _factor_universe_worker_batch_execution_recipe(packet: dict[str, Any], now: str) -> dict[str, Any]:
    dry_run = packet.get("universe_worker_batch_dry_run_receipt") if isinstance(packet.get("universe_worker_batch_dry_run_receipt"), dict) else {}
    activation = packet.get("universe_execution_activation_receipt") if isinstance(packet.get("universe_execution_activation_receipt"), dict) else {}
    scope_ticket = _dict(dry_run.get("worker_batch_scope_ticket"))
    scope_hash_short = str(dry_run.get("worker_batch_scope_hash_short") or scope_ticket.get("scope_hash_short") or "")
    requested_stages = [
        str(item)
        for item in (dry_run.get("requested_stages") if isinstance(dry_run.get("requested_stages"), list) else [])
        if item
    ]
    required_stage_set = set(FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)
    requested_stage_set = set(requested_stages)
    scope_ticket_ready = bool(
        dry_run.get("schema_version") == "factor_universe_worker_batch_dry_run.v1"
        and dry_run.get("preflight_ready_for_explicit_worker_batch_task") is True
        and scope_hash_short
        and required_stage_set <= requested_stage_set
    )
    activation_ready = bool(activation.get("ready_for_explicit_worker_batch_task") is True)
    recipe_ready = scope_ticket_ready
    status = (
        "factor_universe_worker_batch_execution_recipe_ready_execution_pending"
        if recipe_ready
        else "factor_universe_worker_batch_execution_recipe_blocked_scope_or_activation"
    )
    phase_status = {
        "scope_ticket_review": "ready_scope_ticket_visible" if scope_ticket_ready else "blocked_missing_worker_batch_scope_ticket",
        "explicit_worker_task_creation": "pending_explicit_post_worker_batch_research",
        "worker_runtime_binding": "pending_worker_runtime_binding_and_task_log_evidence",
        "storage_read_execution": "pending_worker_storage_read_execution",
        "cross_sectional_rank_execution": "pending_worker_rank_execution",
        "zscore_execution": "pending_worker_zscore_execution",
        "neutralization_execution": "pending_worker_neutralization_execution",
        "factor_combination_execution": "pending_worker_factor_combination_execution",
        "result_summary_persistence": "pending_result_summary_persistence",
        "production_promotion_review": "blocked_until_worker_results_are_reviewed",
    }
    evidence_by_phase = {
        "scope_ticket_review": "approved worker-batch dry-run scope ticket",
        "explicit_worker_task_creation": "explicit worker task_id bound to scope hash",
        "worker_runtime_binding": "worker runtime binding and durable task log evidence",
        "storage_read_execution": "storage read execution evidence for factor_values/daily/daily_basic/moneyflow/trade_cal",
        "cross_sectional_rank_execution": "cross-sectional rank output rows",
        "zscore_execution": "zscore output rows",
        "neutralization_execution": "industry and market-cap neutralization output",
        "factor_combination_execution": "factor combination research output",
        "result_summary_persistence": "persisted result summary with safe row counts and hashes",
        "production_promotion_review": "manual promotion review confirming research-only boundaries",
    }
    rows = [
        _factor_universe_worker_batch_execution_recipe_row(
            phase_key,
            phase_status[phase_key],
            recipe_ready,
            evidence_by_phase[phase_key],
            "Run this phase only through a future explicit worker-backed task; never from GET cache or React render.",
        )
        for phase_key in FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES
    ]
    return {
        "schema_version": "factor_universe_worker_batch_execution_recipe.v1",
        "status": status,
        "scope": "local_factor_universe_worker_batch_execution_recipe_no_worker_or_provider_execution",
        "created_at": now,
        "ltg": "LTG-04/LTG-11/LTG-12",
        "local_recipe_ready": recipe_ready,
        "execution_recipe_ready": recipe_ready,
        "scope_ticket_ready": scope_ticket_ready,
        "activation_ready_for_worker_batch": activation_ready,
        "worker_batch_scope_hash_short": scope_hash_short,
        "universe_mode": dry_run.get("universe_mode"),
        "symbol_count": int(dry_run.get("symbol_count") or 0),
        "phase_keys": list(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
        "pending_phases": list(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
        "phase_count": len(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
        "pending_phase_count": len(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
        "allowed_execution_sequence": list(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
        "required_evidence": [
            "approved worker-batch dry-run scope ticket",
            "explicit worker task_id bound to scope hash",
            "durable task log rows",
            "storage read execution evidence",
            "cross-sectional rank and zscore output",
            "industry and market-cap neutralization output",
            "factor combination research output",
            "persisted result summary with safe hashes",
            "manual promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_recipe_as_worker_execution_evidence",
            "create worker task from GET cache",
            "start worker from GET cache",
            "call Tushare or DeepSeek from this recipe",
            "call GitHub from this recipe",
            "compute rank/zscore in React",
            "mutate strategy action",
            "real trade execution",
            "mark production Factor universe complete from recipe",
        ],
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "storage_read_executed": False,
        "large_universe_pipeline_done": False,
        "cross_sectional_rank_zscore_done": False,
        "zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "result_summary_persisted": False,
        "full_pool_validation_done": False,
        "production_factor_universe_complete": False,
        "partial_pool_is_full_market_proof": False,
        "page_render_starts_full_pool": False,
        "frontend_computes_rank_zscore": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "credential_value_exposed": False,
        "env_key_name_exposed": False,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_factor_universe_worker_batch_execution_recipe",
                "request_params_safe": {
                    "scope": "local_factor_universe_worker_batch_execution_recipe_no_worker_or_provider_execution",
                    "scope_ticket_ready": scope_ticket_ready,
                    "activation_ready_for_worker_batch": activation_ready,
                    "execution_recipe_ready": recipe_ready,
                    "worker_batch_scope_hash_short": scope_hash_short,
                    "phase_count": len(FACTOR_UNIVERSE_WORKER_BATCH_EXECUTION_PHASES),
                    "production_factor_universe_complete": False,
                },
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": now,
                "call_status": "local_recipe_ready_execution_pending" if recipe_ready else "local_recipe_blocked_scope_or_activation",
                "error_message_safe": "",
                **_local_ledger_boundary(),
            }
        ],
        "note": "This local recipe fixes the future worker-backed Factor universe execution order. It does not create worker tasks, start workers, call providers/models, compute production metrics, execute trades, or mutate strategy action.",
    }


def _attach_factor_universe_worker_batch_execution_recipe(packet: dict[str, Any], now: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recipe = _factor_universe_worker_batch_execution_recipe(packet, now)
    packet["universe_worker_batch_execution_recipe"] = recipe
    packet["universe_worker_batch_execution_rows"] = list(recipe.get("rows") or [])
    contract = packet.get("universe_research_contract")
    if isinstance(contract, dict):
        contract["worker_batch_execution_recipe_status"] = recipe["status"]
        contract["worker_batch_execution_recipe_ready"] = bool(recipe.get("local_recipe_ready"))
        contract["worker_batch_execution_recipe_is_not_execution"] = True
        contract["worker_task_created"] = False
        contract["worker_task_executed"] = False
        contract["worker_started"] = False
        contract["large_universe_pipeline_done"] = False
        contract["cross_sectional_rank_zscore_done"] = False
        contract["neutralization_done"] = False
        contract["factor_combination_research_done"] = False
        contract["production_factor_universe_complete"] = False
        contract["external_calls_triggered"] = False
        contract["tushare_called"] = False
        contract["deepseek_called"] = False
        contract["github_called"] = False
    return packet, list(recipe.get("call_ledger") or [])


def run_factor_universe_worker_batch_dry_run_task(payload: Any = None) -> dict[str, Any]:
    now = _now_iso()
    payload_safe = _factor_universe_worker_batch_dry_run_payload(payload, now)
    receipt, rows = _factor_universe_worker_batch_dry_run_receipt(payload_safe, now)
    payload_safe["universe_worker_batch_dry_run_receipt"] = receipt
    payload_safe["universe_worker_batch_dry_run_rows"] = rows
    task = create_task_record(
        "run_factor_universe_worker_batch_dry_run",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload_safe,
        current_step="factor_universe_worker_batch_dry_run_queued",
        warnings=[
            "Factor Universe worker-batch dry-run 只生成本地 scope ticket，不启动 worker，不调用 Tushare、DeepSeek 或 GitHub。",
            "dry-run 不计算生产 rank/zscore/neutralization，不修改 strategy action，不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="building_factor_universe_worker_batch_scope_ticket")
    try:
        hub = dict(read_factor_quant_cache())
        universe_contract = hub.get("universe_research_contract") if isinstance(hub.get("universe_research_contract"), dict) else {}
        universe_contract = dict(universe_contract)
        universe_contract.update(
            {
                "worker_batch_dry_run_ready": bool(receipt.get("local_dry_run_ready")),
                "worker_batch_scope_ticket_ready": bool(receipt.get("worker_batch_scope_hash_short")),
                "worker_batch_dry_run_is_not_execution": True,
                "worker_execution_implemented": False,
                "large_universe_pipeline_done": False,
                "full_pool_validation_done": False,
                "cross_sectional_rank_zscore_done": False,
                "neutralization_done": False,
                "factor_combination_research_done": False,
                "production_factor_universe_complete": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
        hub["universe_research_contract"] = universe_contract
        hub["universe_worker_batch_dry_run_receipt"] = receipt
        hub["universe_worker_batch_dry_run_rows"] = rows
        hub["universe_worker_batch_dry_run_call_ledger"] = list(receipt.get("call_ledger") or [])
        hub["call_ledger"] = list(receipt.get("call_ledger") or []) + list(hub.get("call_ledger") if isinstance(hub.get("call_ledger"), list) else [])
        warning = "Factor Universe worker-batch dry-run ticket 已生成：本地 preflight，不启动 worker，不代表全市场/大股票池生产研究完成。"
        existing_warnings = hub.get("warnings") if isinstance(hub.get("warnings"), list) else []
        hub["warnings"] = [warning] + [item for item in existing_warnings if item != warning]
        hub["external_calls_triggered"] = False
        hub["tushare_called"] = False
        hub["deepseek_called"] = False
        hub["github_called"] = False
        hub["does_not_execute_trades"] = True
        hub["does_not_modify_strategy_action"] = True
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
    except Exception as exc:
        payload_safe["cache_write_error_safe"] = str(exc).splitlines()[0][:240]
    updated = update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(receipt.get("status") or "factor_universe_worker_batch_dry_run_ready"),
        call_ledger=list(receipt.get("call_ledger") or []),
    ) or task
    updated["payload_safe"] = payload_safe
    return updated


def _snapshot_value(snapshot: dict[str, Any], key: str) -> Any:
    return snapshot.get(key)


def _target_from_payload_or_snapshot(payload: Any, snapshot: dict[str, Any]) -> str:
    if isinstance(payload, dict):
        for key in ("ts_code", "ticker", "symbol"):
            if payload.get(key):
                return str(payload[key])
    for packet_key in ("moneyflow_packet", "strategy_packet", "decision_packet", "projection_packet"):
        packet = snapshot.get(packet_key)
        if isinstance(packet, dict):
            for key in ("ticker", "target", "ts_code"):
                if packet.get(key):
                    return str(packet[key])
    return "current_target"


def _local_snapshot_call_ledger(snapshot: dict[str, Any], now: str) -> list[dict[str, Any]]:
    loaded_keys = [
        key
        for key in (
            "moneyflow_packet",
            "hard_risk_packet",
            "limit_emotion_packet",
            "chip_packet",
            "strategy_packet",
            "decision_packet",
            "quant_packet",
            "a_share_fact_lineage_summary",
        )
        if key in snapshot
    ]
    return [
        {
            "api": "local_snapshot_cache",
            "request_params_safe": {"packet_keys": loaded_keys},
            "row_count": len(loaded_keys),
            "data_date": snapshot.get("timestamp"),
            "local_fetched_at": now,
            "call_status": "cache_read" if loaded_keys else "cache_missing",
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _factor_values_storage_call_ledger(result: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        "api": "local_parquet_factor_values",
        "request_params_safe": {
            "dataset": "factor_values",
            "path": result.get("path"),
        },
        "row_count": int(result.get("row_count") or 0),
        "data_date": None,
        "local_fetched_at": now,
        "call_status": result.get("status") or "unknown",
        "error_message_safe": str(result.get("error_message_safe") or "")[:240],
        **_local_ledger_boundary(),
    }


def _build_light_hub_from_snapshot(payload: Any = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = _now_iso()
    snapshot = packet_service.load_snapshot_cache()
    target = _target_from_payload_or_snapshot(payload, snapshot)
    universe = {"type": "current_target", "items": [target], "size": 1}
    library = factor_research.build_factor_library_packet(now=now)
    ledger = factor_research.build_factor_data_ledger_packet(factor_library=library, now=now)
    call_ledger = _local_snapshot_call_ledger(snapshot, now)
    hub = factor_research.build_factor_quant_hub_packet(
        mode="light",
        universe=universe,
        factor_library=library,
        data_ledger=ledger,
        daily_close_packet=_snapshot_value(snapshot, "command_center_daily_close_packet"),
        daily_basic_packet=_snapshot_value(snapshot, "command_center_daily_basic_packet"),
        trade_calendar_packet=_snapshot_value(snapshot, "command_center_trade_calendar_packet") or _snapshot_value(snapshot, "trade_cal_packet") or _snapshot_value(snapshot, "trade_calendar_packet"),
        moneyflow_packet=_snapshot_value(snapshot, "moneyflow_packet"),
        hard_risk_packet=_snapshot_value(snapshot, "hard_risk_packet"),
        limit_emotion_packet=_snapshot_value(snapshot, "limit_emotion_packet"),
        chip_packet=_snapshot_value(snapshot, "chip_packet"),
        a_share_fact_lineage_summary=_snapshot_value(snapshot, "a_share_fact_lineage_summary"),
        next_session_projection_packet=_snapshot_value(snapshot, next_session_projection.PACKET_KEY),
        strategy_execution_packet=_snapshot_value(snapshot, "strategy_packet"),
        decision_packet=_snapshot_value(snapshot, "decision_packet"),
        legacy_quant_packet=_snapshot_value(snapshot, "quant_packet"),
        chokepoint_packet=_snapshot_value(snapshot, "command_center_chokepoint_scan_packet"),
        serenity_packet=serenity_radar.build_serenity_method_radar_packet(now=now),
        now=now,
    )
    hub["cache_source"] = "local_factor_light_pipeline"
    hub["source_snapshot_available"] = bool(snapshot)
    hub["task_call_ledger"] = call_ledger
    hub["tushare_called"] = False
    hub["deepseek_called"] = False
    hub["external_calls_triggered"] = False
    hub["does_not_modify_strategy_action"] = True
    hub["does_not_execute_trades"] = True
    return hub, call_ledger


def run_factor_light_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_factor_light",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
        current_step="factor_light_queued",
        warnings=[
            "light mode 仅读取本地 cache/snapshot，不跑全市场回测。",
            "本地 fallback 不调用 Tushare、DeepSeek、GitHub，也不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="reading_local_snapshot_cache")
    try:
        hub, call_ledger = _build_light_hub_from_snapshot(payload)
        update_task_status(task["task_id"], status="running", progress=0.55, current_step="writing_factor_values_parquet", call_ledger=call_ledger)
        storage_result = storage_service.persist_factor_values_from_hub(hub)
        storage_ledger = _factor_values_storage_call_ledger(storage_result, _now_iso())
        combined_ledger = list(call_ledger) + [storage_ledger]
        hub["factor_values_storage"] = storage_result
        hub["storage_call_ledger"] = [storage_ledger]
        hub["task_call_ledger"] = combined_ledger
        hub["call_ledger"] = combined_ledger
        hub["tushare_called"] = False
        hub["deepseek_called"] = False
        hub["external_calls_triggered"] = False
        hub["deepseek_explain_governance"] = _deepseek_explain_governance(payload=payload)
        update_task_status(task["task_id"], status="running", progress=0.8, current_step="writing_factor_quant_hub_cache", call_ledger=combined_ledger)
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        auto_task = None
        if hub["deepseek_explain_governance"]["auto_after_task"]:
            universe = hub.get("universe") if isinstance(hub.get("universe"), dict) else {}
            universe_items = universe.get("items") if isinstance(universe.get("items"), list) else []
            auto_task = run_factor_deepseek_explanation_task({
                "trigger": "auto_after_run_light",
                "auto_after_task": True,
                "ts_code": str(universe_items[0]) if universe_items else "",
            })
            latest_hub = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_factor_quant_hub_packet")
            if isinstance(latest_hub, dict):
                hub = latest_hub
            hub.setdefault("deepseek_explain_governance", _deepseek_explain_governance(payload=payload))
            hub["deepseek_explain_governance"]["auto_after_task_queued"] = True
            hub["deepseek_explain_governance"]["auto_after_task_id"] = auto_task.get("task_id")
            SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        final_warning = ""
        if auto_task:
            final_warning = f"auto_after_task_created:{auto_task.get('task_id')}"
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="factor_light_completed_from_local_cache",
            call_ledger=combined_ledger,
            warning=final_warning or None,
        ) or task
    except Exception as exc:
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="factor_light_failed",
            error_message_safe=str(exc)[:500],
        ) or task


def run_factor_universe_research_plan_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_factor_universe_research_plan",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=_factor_universe_task_payload_summary(payload),
        current_step="factor_universe_research_plan_queued",
        warnings=[
            "Factor universe 读取计划只消费本地 DuckDB/Parquet 查询合同，不调用 Tushare、DeepSeek 或 GitHub。",
            "本任务不跑 full-pool 因子研究，不计算 strategy action，不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="reading_local_storage_query_contracts")
    now = _now_iso()
    call_ledger: list[dict[str, Any]] = []
    try:
        plan = _build_factor_universe_research_read_plan(payload, now)
        call_ledger = _factor_universe_read_plan_call_ledger(plan, now)
        update_task_status(
            task["task_id"],
            status="running",
            progress=0.65,
            current_step="writing_factor_universe_read_plan_cache",
            call_ledger=call_ledger,
        )
        hub = dict(read_factor_quant_cache())
        universe_contract = hub.get("universe_research_contract") if isinstance(hub.get("universe_research_contract"), dict) else {}
        universe_contract = dict(universe_contract)
        universe_contract.update(
            {
                "storage_query_contract_consumed": True,
                "worker_task_consumption_plan_ready": True,
                "requested_universe_mode": plan["requested_universe_mode"],
                "storage_query_contract_count": plan["storage_query_contract_count"],
                "large_universe_pipeline_done": False,
                "full_pool_validation_done": False,
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
        existing_ledger = hub.get("call_ledger") if isinstance(hub.get("call_ledger"), list) else []
        existing_warnings = hub.get("warnings") if isinstance(hub.get("warnings"), list) else []
        plan_warning = "Factor Universe 任务化读取计划已生成：只读本地 storage 合同，不代表 full-pool 生产验收完成。"
        hub["universe_research_contract"] = universe_contract
        hub["universe_research_task_plan"] = plan
        hub["universe_research_task_plan_rows"] = list(plan.get("storage_query_rows") or [])
        hub = _attach_factor_universe_execution_readiness(hub)
        hub["universe_research_task_call_ledger"] = call_ledger
        hub["call_ledger"] = call_ledger + list(existing_ledger)
        hub["warnings"] = [plan_warning] + [item for item in existing_warnings if item != plan_warning]
        hub["external_calls_triggered"] = False
        hub["tushare_called"] = False
        hub["deepseek_called"] = False
        hub["github_called"] = False
        hub["does_not_execute_trades"] = True
        hub["does_not_modify_strategy_action"] = True
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="factor_universe_research_plan_ready",
            call_ledger=call_ledger,
        ) or task
    except Exception as exc:
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="factor_universe_research_plan_failed",
            error_message_safe=str(exc)[:500],
            call_ledger=call_ledger,
        ) or task


def _extract_provided_explanation_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in ("provided_explanation", "local_explanation_payload", "mock_deepseek_output", "deepseek_response"):
        if key in payload:
            return payload.get(key)
    return None


def _deepseek_task_payload_summary(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "provided_explanation_payload": _extract_provided_explanation_payload(payload) is not None,
    }
    if isinstance(payload, dict):
        for key in ("ts_code", "ticker", "symbol"):
            if payload.get(key):
                summary[key] = str(payload.get(key))
    return summary


def _deepseek_model_strategy(purpose: str = "factor_explain") -> dict[str, Any]:
    return model_strategy_service.build_deepseek_model_strategy_ref(purpose)


def _deepseek_explanation_call_ledger(
    now: str,
    *,
    sanitized_payload: bool,
    input_hash: str = "",
    token_estimate: int = 0,
    output_hash: str = "",
    parse_failed: bool | None = None,
    model_call_status: str = "not_called",
    cache_key: dict[str, Any] | None = None,
    call_status_override: str | None = None,
) -> list[dict[str, Any]]:
    strategy = _deepseek_model_strategy("factor_explain")
    call_status = "not_called"
    if sanitized_payload:
        call_status = "provided_payload_parse_failed" if parse_failed else "provided_payload_sanitized"
    if call_status_override:
        call_status = call_status_override
    governance = _deepseek_explain_governance()
    return [
        {
            "api": "deepseek_factor_explanation",
            "request_params_safe": {
                "mode": governance["mode"],
                "auto_after_task": governance["auto_after_task"],
                "configured_auto_after_task": governance["configured_auto_after_task"],
                "provided_explanation_payload": sanitized_payload,
                "validation_mode": "local_sanitizer_only",
                "model_used": strategy.get("model"),
                "model_purpose": strategy.get("purpose"),
                "model_call_status": model_call_status,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "token_estimate": token_estimate,
                "parse_failed": parse_failed if parse_failed is not None else False,
                "cache_key": cache_key or {},
                "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
                "deepseek_model_strategy": strategy,
            },
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": call_status,
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _deepseek_prompt_preview(hub: dict[str, Any]) -> dict[str, Any]:
    prompt = factor_research.build_factor_deepseek_explanation_prompt(hub)
    strategy = _deepseek_model_strategy("factor_explain")
    user_prompt = str(prompt.get("user_prompt") or "")
    return {
        "status": "ready_not_sent",
        "model_used": strategy.get("model"),
        "deepseek_model_strategy": strategy,
        "input_hash": prompt.get("input_hash"),
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "token_estimate": prompt.get("token_estimate"),
        "json_object_instruction_present": "JSON object" in user_prompt,
        "allowed_top_level_keys": prompt.get("allowed_top_level_keys") or [],
        "would_enter_deepseek_prompt_if_user_authorizes": bool(prompt.get("enters_deepseek_prompt")),
        "enters_deepseek_prompt": False,
        "does_not_include_full_packet": bool(prompt.get("does_not_include_full_packet")),
        "does_not_include_price_or_position": True,
        "does_not_include_factor_values": True,
    }


def _deepseek_validation_summary(
    *,
    explanation: dict[str, Any],
    prompt_preview: dict[str, Any],
    model_strategy: dict[str, Any],
) -> dict[str, Any]:
    ignored_keys = explanation.get("ignored_keys") if isinstance(explanation.get("ignored_keys"), list) else []
    return {
        "status": explanation.get("status") or "not_called",
        "validation_mode": "local_sanitizer_only",
        "model_used": model_strategy.get("model"),
        "model_purpose": model_strategy.get("purpose"),
        "model_call_status": explanation.get("model_call_status") or "not_called",
        "input_hash": explanation.get("input_hash") or prompt_preview.get("input_hash") or "",
        "output_hash": explanation.get("output_hash") or "",
        "cache_key": explanation.get("cache_key") or {},
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "explain_governance": _deepseek_explain_governance(),
        "prompt_token_estimate": prompt_preview.get("token_estimate") or 0,
        "output_token_estimate": explanation.get("token_estimate") or 0,
        "parse_failed": bool(explanation.get("parse_failed")),
        "allowed_top_level_keys": prompt_preview.get("allowed_top_level_keys") or [],
        "ignored_key_count": len(ignored_keys),
        "ignored_keys": sorted(str(key) for key in ignored_keys),
        "invalid_output_discarded": bool(explanation.get("parse_failed")),
        "does_not_override_numeric_values": explanation.get("does_not_override_numeric_values") is not False,
        "does_not_output_strategy_action": explanation.get("does_not_output_strategy_action") is not False,
        "does_not_modify_strategy_action": True,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
    }


def run_factor_deepseek_explanation_task(payload: Any = None) -> dict[str, Any]:
    governance = _deepseek_explain_governance(payload=payload)
    task = create_task_record(
        "run_deepseek_factor_explanation",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=_deepseek_task_payload_summary(payload),
        current_step="deepseek_explanation_queued",
        warnings=[
            "DeepSeek 因子解释任务本轮不调用模型；由治理模式控制，只准备安全 prompt 或清洗已提供的解释 JSON。",
            "解释输出只允许六个白名单字段，不覆盖因子数值、价格、持仓或 strategy action。",
            f"DeepSeek explanation mode: {governance['mode']}；auto_after_task={governance['auto_after_task']}。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    if governance["disabled"]:
        ledger = _deepseek_explanation_call_ledger(
            _now_iso(),
            sanitized_payload=False,
            model_call_status="disabled",
            call_status_override="disabled_by_governance",
        )
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_explanation_disabled_by_governance",
            error_message_safe="deepseek_factor_explain_disabled",
            call_ledger=ledger,
        ) or task
    update_task_status(task["task_id"], status="running", progress=0.2, current_step="reading_factor_quant_hub_cache")
    now = _now_iso()
    call_ledger = _deepseek_explanation_call_ledger(now, sanitized_payload=False)
    try:
        hub = dict(read_factor_quant_cache())
        update_task_status(task["task_id"], status="running", progress=0.45, current_step="building_guarded_deepseek_prompt_preview")
        prompt_preview = _deepseek_prompt_preview(hub)
        model_strategy = _deepseek_model_strategy("factor_explain")
        input_hash = str(prompt_preview.get("input_hash") or "")
        token_estimate = int(prompt_preview.get("token_estimate") or 0)
        model_used = str(model_strategy.get("model") or "")
        cache_key = _deepseek_explanation_cache_key(hub, input_hash=input_hash, model_name=model_used)
        call_ledger = _deepseek_explanation_call_ledger(
            now,
            sanitized_payload=False,
            input_hash=input_hash,
            token_estimate=token_estimate,
            cache_key=cache_key,
        )
        provided_payload = _extract_provided_explanation_payload(payload)
        existing_key = hub.get("deepseek_explanation_cache_key")
        existing_explanation = hub.get("deepseek_explanation") if isinstance(hub.get("deepseek_explanation"), dict) else {}
        if provided_payload is None and _same_deepseek_cache_key(existing_key, cache_key) and existing_explanation.get("status") in {"success", "parse_failed"}:
            call_ledger = _deepseek_explanation_call_ledger(
                now,
                sanitized_payload=False,
                input_hash=input_hash,
                token_estimate=token_estimate,
                cache_key=cache_key,
                call_status_override="cache_hit_no_duplicate_model_call",
            )
            hub["deepseek_explain_governance"] = governance
            hub["deepseek_explanation_cache_key"] = cache_key
            hub["deepseek_explanation_cache_hit"] = True
            hub = _attach_deepseek_json_stability_audit(hub, governance=governance)
            update_task_status(task["task_id"], status="running", progress=0.75, current_step="deepseek_explanation_cache_hit", call_ledger=call_ledger)
            SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
            return update_task_status(
                task["task_id"],
                status="success",
                progress=1.0,
                current_step="deepseek_explanation_cache_hit_no_model_call",
                call_ledger=call_ledger,
            ) or task
        if provided_payload is None:
            explanation = {
                "called": False,
                "status": "not_called",
                "parse_failed": False,
                "payload": None,
                "ignored_keys": [],
                "error_message_safe": "",
                "model_used": model_used,
                "input_hash": input_hash,
                "output_hash": "",
                "token_estimate": 0,
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "model_call_status": "not_called",
                "source": "prompt_ready_no_model_call",
                "cache_key": cache_key,
                "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
                "deepseek_model_strategy": model_strategy,
            }
            current_step = "deepseek_prompt_ready_without_model_call"
        else:
            explanation = factor_research.sanitize_factor_deepseek_explanation(provided_payload, model_used=model_used, input_hash=input_hash)
            explanation["called"] = False
            explanation["model_call_status"] = "not_called"
            explanation["source"] = "provided_payload_sanitized_no_model_call"
            explanation["allowed_keys_enforced"] = True
            explanation["deepseek_model_strategy"] = model_strategy
            explanation["cache_key"] = cache_key
            explanation["prompt_version"] = DEEPSEEK_FACTOR_PROMPT_VERSION
            call_ledger = _deepseek_explanation_call_ledger(
                now,
                sanitized_payload=True,
                input_hash=input_hash,
                token_estimate=token_estimate,
                output_hash=str(explanation.get("output_hash") or ""),
                parse_failed=bool(explanation.get("parse_failed")),
                model_call_status=str(explanation.get("model_call_status") or "not_called"),
                cache_key=cache_key,
            )
            current_step = "deepseek_explanation_sanitized_without_model_call"

        hub["deepseek_explain_governance"] = governance
        hub["deepseek_explanation_cache_key"] = cache_key
        hub["deepseek_explanation_cache_hit"] = False
        hub["deepseek_explanation_prompt_preview"] = prompt_preview
        hub["deepseek_explanation"] = explanation
        hub["deepseek_validation_summary"] = _deepseek_validation_summary(
            explanation=explanation,
            prompt_preview=prompt_preview,
            model_strategy=model_strategy,
        )
        hub = _attach_deepseek_json_stability_audit(
            hub,
            prompt_preview=prompt_preview,
            validation_summary=hub["deepseek_validation_summary"],
            governance=governance,
        )
        hub["deepseek_model_strategy"] = model_strategy
        hub["deepseek_called"] = False
        hub["deepseek_model_called"] = False
        hub["deepseek_task_external_calls_triggered"] = False
        hub["deepseek_call_ledger"] = call_ledger
        hub["does_not_modify_strategy_action"] = True
        hub["does_not_modify_next_session_operation_zones"] = True
        hub["does_not_execute_trades"] = True

        update_task_status(task["task_id"], status="running", progress=0.75, current_step="writing_guarded_deepseek_explanation_cache", call_ledger=call_ledger)
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step=current_step,
            call_ledger=call_ledger,
        ) or task
    except Exception as exc:
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_explanation_failed",
            error_message_safe=str(exc)[:500],
            call_ledger=call_ledger,
        ) or task


def create_factor_task(task_type: str, payload: Any = None) -> dict[str, Any]:
    if task_type == "refresh_factor_data":
        return tushare_task_service.run_tushare_refresh_task(
            payload,
            task_type="refresh_factor_data",
            output_packet_key="command_center_factor_quant_hub_packet",
            default_apis=("daily", "daily_basic", "moneyflow"),
        )
    if task_type == "run_factor_light":
        return run_factor_light_task(payload)
    if task_type == "run_factor_universe_research_plan":
        return run_factor_universe_research_plan_task(payload)
    if task_type == "run_factor_universe_worker_batch_dry_run":
        return run_factor_universe_worker_batch_dry_run_task(payload)
    if task_type == "run_factor_test_provider_small_pool_acceptance_dry_run":
        return run_factor_test_provider_small_pool_acceptance_dry_run_task(payload)
    if task_type == "run_deepseek_factor_explanation":
        return run_factor_deepseek_explanation_task(payload)
    return create_task_stub(
        task_type,
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
        current_step="factor_quant_task_stub_created",
    )
