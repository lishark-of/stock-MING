#!/usr/bin/env python3
"""Validate the local LTG-13 Candidate Radar contract.

This push-gate guard is not a production radar scan. It reads local cache and
builds local plan-only and local-universe execution contracts to prevent quick
scans, full-pool plans, local full-pool execution receipts, deep-scan plans,
search quant projection receipts, no-feature-loss QA, replacement triage, and
result-delta clarity from being mistaken for production radar replacement,
provider/model execution, or buy signals.
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

from server.services import candidate_service, packet_service, task_service  # noqa: E402


REQUIRED_TASK_TYPES = {
    "run_candidate_radar_quick_scan",
    "run_candidate_radar_quant_projection",
    "run_candidate_radar_full_pool_plan",
    "run_candidate_radar_full_pool_local_scan",
    "run_candidate_radar_deep_scan_plan",
    "run_candidate_radar_deep_scan_local_review",
    "run_candidate_radar_browser_qa_review",
}
REQUIRED_NO_FEATURE_LOSS_GAPS = {
    "browser_performance_trace_pending",
    "full_pool_execution_pending",
    "deep_scan_execution_pending",
    "provider_backed_acceptance_pending",
}
REQUIRED_REPLACEMENT_GAPS = {
    "browser_visual_delta_qa",
    "browser_performance_trace",
    "full_pool_worker_execution",
    "deep_scan_execution",
    "provider_backed_acceptance",
}
REQUIRED_PROMOTION_ROWS = {
    "legacy_retirement_triage_clear",
    "provider_signal_coverage_complete",
    "browser_visual_and_performance_reviewed",
    "runtime_budget_ready_not_perf_trace",
    "full_pool_execution_complete",
    "deep_scan_execution_complete",
}
REQUIRED_PROMOTION_BLOCKERS = REQUIRED_PROMOTION_ROWS - {"browser_visual_and_performance_reviewed"}
REQUIRED_ACTIVATION_BLOCKERS = {
    "production_promotion_blocked_visible",
    "full_pool_worker_execution_required",
    "deep_scan_worker_execution_required",
    "provider_backed_acceptance_required",
    "browser_visual_performance_review_required",
    "legacy_retirement_stays_blocked",
}
REQUIRED_PARITY_ACCEPTANCE_ITEMS = {
    "top_watch_excluded_split",
    "evidence_links",
    "scoring_dimensions",
    "trigger_invalidation",
    "holding_comparison",
    "candidate_pool_sources",
    "scan_filters",
    "timeout_and_fallback",
    "manual_deep_research",
}
CANDIDATE_BROWSER_QA_RUNBOOK_PATH = "scripts/candidate_radar_browser_qa_runbook.py"


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


def _task_catalog_rows() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("task_type") or ""): dict(row)
        for row in task_service.TASK_CATALOG
        if isinstance(row, dict) and row.get("task_type") in REQUIRED_TASK_TYPES
    }


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _snapshot_map() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = candidate_service._safe_value(snapshot)
    return safe_snapshot if isinstance(safe_snapshot, dict) else {}


def _contract_snapshot_with_candidates(snapshot_map: dict[str, Any]) -> dict[str, Any]:
    if _list(snapshot_map.get("next_ticket_candidates")):
        return snapshot_map
    fixture = dict(snapshot_map)
    fixture["next_ticket_candidates"] = [
        {
            "symbol": "000001.SZ",
            "name": "contract_candidate_a",
            "score": 72,
            "trigger_condition": "local evidence trigger present",
            "invalidation_condition": "local invalidation present",
            "data_gaps": ["provider_backed_acceptance_pending"],
            "evidence": ["local cache row"],
        },
        {
            "symbol": "000002.SZ",
            "name": "contract_candidate_b",
            "score": 68,
            "trigger_condition": "local trigger present",
            "invalidation_condition": "local invalidation present",
            "data_gaps": ["deep_scan_acceptance_pending"],
            "evidence": ["local cache row"],
        },
    ]
    return fixture


def build_contract() -> dict[str, Any]:
    now = "2026-06-13T10:00:00"
    snapshot_map = _snapshot_map()
    contract_snapshot = _contract_snapshot_with_candidates(snapshot_map)
    cache_packet = candidate_service.read_candidate_radar_cache()
    full_pool_plan = candidate_service._build_full_pool_scan_plan(contract_snapshot, {}, now=now)
    local_universe_packet = candidate_service._build_candidate_radar_packet(
        contract_snapshot,
        mode="full_pool_local_scan",
        cache_source="local_contract",
        scan_mode="full_pool_local_scan",
        request_params_safe={"local_execution_only": True, "external_sources_allowed": False},
        local_pool_audit={
            "scan_mode": "full_pool_local_scan",
            "input_source": "local_contract_fixture",
            "input_candidate_count": 2,
            "normalized_candidate_count": 2,
            "truncated_candidate_count": 0,
            "max_local_candidates": candidate_service.FULL_POOL_LOCAL_INPUT_LIMIT,
        },
        full_pool_scan_plan=full_pool_plan,
    )
    deep_scan_plan = candidate_service._build_deep_scan_plan(contract_snapshot, {}, now=now)
    plan_packet = candidate_service._build_candidate_radar_packet(
        contract_snapshot,
        mode="local_contract_plan",
        cache_source="local_contract",
        scan_mode="deep_scan_plan",
        request_params_safe={"plan_only": True, "external_sources_allowed": False},
        full_pool_scan_plan=full_pool_plan,
        deep_scan_plan=deep_scan_plan,
    )
    local_deep_review_packet = candidate_service._build_candidate_radar_packet(
        contract_snapshot,
        mode="deep_scan_local_review",
        cache_source="local_contract",
        scan_mode="deep_scan_local_review",
        request_params_safe={"local_review_only": True, "external_sources_allowed": False},
        full_pool_scan_plan=full_pool_plan,
        deep_scan_plan=deep_scan_plan,
    )
    quant_snapshot, _, _ = candidate_service._snapshot_with_quant_projection(
        contract_snapshot,
        {"symbol": "000001", "include_tushare": True, "include_deepseek": True},
    )
    quant_packet = candidate_service._build_candidate_radar_packet(
        quant_snapshot,
        mode=candidate_service.QUANT_PROJECTION_SCAN_MODE,
        cache_source="local_contract",
        scan_mode=candidate_service.QUANT_PROJECTION_SCAN_MODE,
        request_params_safe={
            "scan_mode": candidate_service.QUANT_PROJECTION_SCAN_MODE,
            "symbol": "000001.SZ",
            "external_sources_allowed": False,
        },
    )
    readiness = _dict(cache_packet.get("fast_scan_readiness_audit"))
    runtime_budget = _dict(cache_packet.get("fast_scan_runtime_budget_contract"))
    no_loss = _dict(cache_packet.get("no_feature_loss_acceptance_contract"))
    no_loss_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(cache_packet.get("no_feature_loss_acceptance_rows"))
        if isinstance(row, dict)
    }
    triage = _dict(cache_packet.get("replacement_gap_triage_contract"))
    triage_rows = {
        str(row.get("gap_key") or ""): row
        for row in _list(cache_packet.get("replacement_gap_triage_rows"))
        if isinstance(row, dict)
    }
    promotion_audit = _dict(cache_packet.get("candidate_radar_promotion_blocker_audit"))
    promotion_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(cache_packet.get("candidate_radar_promotion_blocker_rows"))
        if isinstance(row, dict)
    }
    activation_receipt = _dict(cache_packet.get("candidate_radar_production_activation_receipt"))
    activation_rows = {
        str(row.get("activation_key") or ""): row
        for row in _list(cache_packet.get("candidate_radar_production_activation_rows"))
        if isinstance(row, dict)
    }
    quick_receipt = _dict(cache_packet.get("quick_scan_execution_receipt"))
    quick_receipt_rows = {
        str(row.get("receipt_key") or ""): row
        for row in _list(cache_packet.get("quick_scan_execution_receipt_rows"))
        if isinstance(row, dict)
    }
    result_delta = _dict(cache_packet.get("result_delta_clarity_contract"))
    priority_explanation = _dict(cache_packet.get("candidate_priority_explanation_contract"))
    legacy_parity_acceptance = _dict(cache_packet.get("legacy_parity_acceptance_receipt"))
    legacy_parity_acceptance_rows = {
        str(row.get("item_key") or ""): row
        for row in _list(cache_packet.get("legacy_parity_acceptance_rows"))
        if isinstance(row, dict)
    }
    full_pool_local_receipt = _dict(local_universe_packet.get("full_pool_local_execution_receipt"))
    full_pool_local_rows = {
        str(row.get("receipt_key") or ""): row
        for row in _list(local_universe_packet.get("full_pool_local_execution_rows"))
        if isinstance(row, dict)
    }
    deep_scan_local_receipt = _dict(local_deep_review_packet.get("deep_scan_local_review_receipt"))
    deep_scan_local_rows = {
        str(row.get("review_key") or ""): row
        for row in _list(local_deep_review_packet.get("deep_scan_local_review_rows"))
        if isinstance(row, dict)
    }
    search_quant_projection_receipt = _dict(quant_packet.get("search_quant_projection_receipt"))
    search_quant_projection_rows = {
        str(row.get("step_key") or ""): row
        for row in _list(quant_packet.get("search_quant_projection_rows"))
        if isinstance(row, dict)
    }
    browser_qa_evidence = _dict(cache_packet.get("candidate_browser_qa_evidence_summary"))
    browser_qa_review = _dict(cache_packet.get("candidate_browser_qa_review_contract"))
    policy = _dict(cache_packet.get("policy"))
    task_rows = _task_catalog_rows()
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/candidate_radar_contract.py")
    browser_qa_runbook = _read_script(CANDIDATE_BROWSER_QA_RUNBOOK_PATH)
    motion_runner = _read_script("scripts/motion_browser_qa_runner.mjs")
    candidate_frontend = _read_script("desktop/src/routes/CandidateRadar.tsx")

    rows = [
        _row(
            "cache_get_is_read_only_no_scan",
            cache_packet.get("packet_key") == candidate_service.PACKET_KEY
            and cache_packet.get("cache_only") is True
            and cache_packet.get("read_only") is True
            and policy.get("does_not_scan_market") is True
            and policy.get("quick_scan_reads_cache_only") is True
            and policy.get("post_task_required_for_scan") is True
            and _flag_false(cache_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and cache_packet.get("does_not_execute_trades") is True
            and cache_packet.get("does_not_modify_strategy_action") is True,
            "GET candidate radar cache must remain local/read-only and must not start market scans or provider/model calls.",
        ),
        _row(
            "task_catalog_button_gates_scan_modes",
            set(task_rows) == REQUIRED_TASK_TYPES
            and task_rows["run_candidate_radar_quick_scan"].get("route") == "POST /api/candidate-radar/scan-quick"
            and task_rows["run_candidate_radar_quick_scan"].get("possible_external_sources") == []
            and set(task_rows["run_candidate_radar_quick_scan"].get("scan_modes") or []) == candidate_service.SUPPORTED_LOCAL_SCAN_MODES
            and task_rows["run_candidate_radar_quant_projection"].get("route")
            == "POST /api/candidate-radar/quant-projection"
            and task_rows["run_candidate_radar_quant_projection"].get("local_receipt_only") is True
            and task_rows["run_candidate_radar_quant_projection"].get("provider_model_pending") is True
            and task_rows["run_candidate_radar_quant_projection"].get("provider_execution_implemented") is False
            and task_rows["run_candidate_radar_quant_projection"].get("model_execution_implemented") is False
            and task_rows["run_candidate_radar_quant_projection"].get("production_quant_projection_complete") is False
            and task_rows["run_candidate_radar_full_pool_plan"].get("route") == "POST /api/candidate-radar/full-pool-plan"
            and task_rows["run_candidate_radar_full_pool_plan"].get("plan_only") is True
            and task_rows["run_candidate_radar_full_pool_plan"].get("full_pool_scan_done") is False
            and task_rows["run_candidate_radar_full_pool_local_scan"].get("route")
            == "POST /api/candidate-radar/full-pool-local-scan"
            and task_rows["run_candidate_radar_full_pool_local_scan"].get("local_execution_only") is True
            and task_rows["run_candidate_radar_full_pool_local_scan"].get("provider_backed_acceptance_done") is False
            and task_rows["run_candidate_radar_full_pool_local_scan"].get("production_full_pool_scan_done") is False
            and task_rows["run_candidate_radar_full_pool_local_scan"].get("provider_refresh_executed") is False
            and task_rows["run_candidate_radar_deep_scan_plan"].get("route") == "POST /api/candidate-radar/deep-scan-plan"
            and task_rows["run_candidate_radar_deep_scan_plan"].get("plan_only") is True
            and task_rows["run_candidate_radar_deep_scan_plan"].get("deep_scan_done") is False
            and task_rows["run_candidate_radar_deep_scan_local_review"].get("route")
            == "POST /api/candidate-radar/deep-scan-local-review"
            and task_rows["run_candidate_radar_deep_scan_local_review"].get("local_review_only") is True
            and task_rows["run_candidate_radar_deep_scan_local_review"].get("deep_scan_done") is False
            and task_rows["run_candidate_radar_deep_scan_local_review"].get("provider_backed_acceptance_done") is False
            and task_rows["run_candidate_radar_deep_scan_local_review"].get("deepseek_called") is False
            and task_rows["run_candidate_radar_browser_qa_review"].get("route")
            == "POST /api/candidate-radar/browser-qa-review"
            and task_rows["run_candidate_radar_browser_qa_review"].get("browser_qa_review_only") is True
            and task_rows["run_candidate_radar_browser_qa_review"].get("opens_browser") is False
            and task_rows["run_candidate_radar_browser_qa_review"].get("writes_artifacts") is False
            and task_rows["run_candidate_radar_browser_qa_review"].get("production_radar_replacement_complete") is False,
            "Candidate radar scan modes must stay button-gated local tasks; full-pool/deep-scan entries are plan-only and browser QA review reads local artifacts only.",
        ),
        _row(
            "full_pool_local_execution_receipt_is_local_not_provider_acceptance",
            full_pool_local_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
            and full_pool_local_receipt.get("status") == "full_pool_local_execution_ready_production_pending"
            and full_pool_local_receipt.get("local_full_pool_execution_done") is True
            and full_pool_local_receipt.get("production_full_pool_scan_done") is False
            and full_pool_local_receipt.get("provider_backed_acceptance_done") is False
            and full_pool_local_receipt.get("worker_backed_execution_done") is False
            and full_pool_local_receipt.get("legacy_retirement_ready") is False
            and full_pool_local_receipt.get("legacy_fallback_required") is True
            and int(full_pool_local_receipt.get("production_blocker_count") or 0) > 0
            and _dict(full_pool_local_rows.get("local_universe_consumed")).get("passed") is True
            and _dict(full_pool_local_rows.get("provider_not_refreshed")).get("production_blocker") is True
            and _dict(full_pool_local_rows.get("production_full_market_acceptance_pending")).get("production_blocker")
            is True
            and "treat_local_full_pool_execution_as_provider_backed_full_market_acceptance"
            in _list(full_pool_local_receipt.get("not_allowed_next_steps"))
            and _flag_false(
                full_pool_local_receipt,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and full_pool_local_receipt.get("does_not_execute_trades") is True
            and full_pool_local_receipt.get("does_not_modify_strategy_action") is True
            and full_pool_local_receipt.get("candidate_is_not_buy_instruction") is True
            and "full_pool_local_execution_receipt" in candidate_frontend
            and "Full-pool 本地执行收据" in candidate_frontend,
            "Local full-pool execution must be visible as a receipt while provider-backed full-market acceptance stays pending.",
        ),
        _row(
            "deep_scan_local_review_receipt_is_local_not_model_execution",
            deep_scan_local_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
            and deep_scan_local_receipt.get("status") == "deep_scan_local_review_ready_production_pending"
            and deep_scan_local_receipt.get("scope") == "explicit_local_candidate_deep_review_not_model_or_provider_execution"
            and deep_scan_local_receipt.get("local_deep_scan_review_done") is True
            and deep_scan_local_receipt.get("deep_scan_done") is False
            and deep_scan_local_receipt.get("deep_scan_validation_done") is False
            and deep_scan_local_receipt.get("provider_backed_acceptance_done") is False
            and deep_scan_local_receipt.get("deepseek_called") is False
            and deep_scan_local_receipt.get("worker_backed_execution_done") is False
            and deep_scan_local_receipt.get("legacy_retirement_ready") is False
            and deep_scan_local_receipt.get("legacy_fallback_required") is True
            and int(deep_scan_local_receipt.get("production_blocker_count") or 0) > 0
            and _dict(deep_scan_local_rows.get("local_candidate_evidence_reviewed")).get("passed") is True
            and _dict(deep_scan_local_rows.get("deepseek_not_called")).get("production_blocker") is True
            and _dict(deep_scan_local_rows.get("production_deep_scan_acceptance_pending")).get("production_blocker") is True
            and "treat_local_deep_review_as_deep_scan_done" in _list(deep_scan_local_receipt.get("not_allowed_next_steps"))
            and "call_deepseek_from_local_review" in _list(deep_scan_local_receipt.get("not_allowed_next_steps"))
            and _flag_false(
                deep_scan_local_receipt,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and deep_scan_local_receipt.get("does_not_execute_trades") is True
            and deep_scan_local_receipt.get("does_not_modify_strategy_action") is True
            and deep_scan_local_receipt.get("candidate_is_not_buy_instruction") is True
            and "postCandidateRadarDeepScanLocalReview" in candidate_frontend
            and "deep_scan_local_review_receipt" in candidate_frontend
            and "Deep-scan 本地审查收据" in candidate_frontend,
            "Deep-scan local review must stay a local evidence review receipt; it must not call DeepSeek/providers or mark deep_scan production acceptance complete.",
        ),
        _row(
            "search_quant_projection_receipt_is_local_provider_model_pending",
            search_quant_projection_receipt.get("schema_version")
            == "candidate_radar_search_quant_projection_receipt.v1"
            and search_quant_projection_receipt.get("status")
            == "quant_projection_local_receipt_ready_provider_model_pending"
            and search_quant_projection_receipt.get("scan_mode") == candidate_service.QUANT_PROJECTION_SCAN_MODE
            and search_quant_projection_receipt.get("symbol") == "000001.SZ"
            and search_quant_projection_receipt.get("symbol_valid") is True
            and search_quant_projection_receipt.get("ready_for_real_provider_model_projection") is False
            and search_quant_projection_receipt.get("provider_execution_implemented") is False
            and search_quant_projection_receipt.get("model_execution_implemented") is False
            and search_quant_projection_receipt.get("factor_refresh_executed") is False
            and search_quant_projection_receipt.get("next_session_refresh_executed") is False
            and search_quant_projection_receipt.get("echarts_payload_refreshed") is False
            and search_quant_projection_receipt.get("production_quant_projection_complete") is False
            and int(search_quant_projection_receipt.get("production_blocker_count") or 0) > 0
            and _dict(search_quant_projection_rows.get("symbol_validation")).get("local_ready") is True
            and _dict(search_quant_projection_rows.get("tushare_light_refresh_pending")).get("production_blocker")
            is True
            and _dict(search_quant_projection_rows.get("deepseek_pro_explanation_pending")).get("production_blocker")
            is True
            and _flag_false(
                search_quant_projection_receipt,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and search_quant_projection_receipt.get("does_not_execute_trades") is True
            and search_quant_projection_receipt.get("does_not_modify_strategy_action") is True
            and search_quant_projection_receipt.get("candidate_is_not_buy_instruction") is True
            and "postCandidateRadarQuantProjection" in candidate_frontend
            and "search_quant_projection_receipt" in candidate_frontend
            and "搜票量化推演" in candidate_frontend
            and "生成 3.0 量化推演" in candidate_frontend,
            "Search quant projection must be a button-gated local receipt with provider/model/factor/chart evidence pending, not a trade signal or external acceptance.",
        ),
        _row(
            "fast_scan_readiness_is_local_pending",
            readiness.get("schema_version") == "candidate_radar_fast_scan_readiness.v1"
            and readiness.get("status") == "fast_scan_local_ready_full_pool_pending"
            and readiness.get("local_fast_scan_ready") is True
            and readiness.get("production_radar_replacement_complete") is False
            and readiness.get("full_pool_scan_done") is False
            and readiness.get("deep_scan_done") is False
            and readiness.get("provider_backed_acceptance_done") is False
            and _flag_false(readiness, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and readiness.get("does_not_execute_trades") is True
            and readiness.get("does_not_modify_strategy_action") is True,
            "Fast scan readiness can be locally ready only while full-pool, deep-scan, and provider acceptance remain pending.",
        ),
        _row(
            "runtime_budget_is_static_not_browser_trace",
            runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1"
            and runtime_budget.get("status") == "fast_scan_runtime_budget_ready"
            and runtime_budget.get("browser_performance_trace_done") is False
            and runtime_budget.get("full_pool_scan_done") is False
            and runtime_budget.get("deep_scan_done") is False
            and runtime_budget.get("cache_get_starts_scan") is False
            and runtime_budget.get("page_render_starts_scan") is False,
            "Runtime budget contract is static/local and cannot be treated as browser performance proof.",
        ),
        _row(
            "no_feature_loss_is_local_not_replacement",
            no_loss.get("schema_version") == "candidate_radar_no_feature_loss_acceptance.v1"
            and no_loss.get("status") == "no_feature_loss_acceptance_local_ready_production_pending"
            and no_loss.get("local_no_feature_loss_contract_ready") is True
            and no_loss.get("production_radar_replacement_complete") is False
            and no_loss.get("legacy_fallback_required") is True
            and no_loss.get("full_pool_scan_done") is False
            and no_loss.get("deep_scan_done") is False
            and no_loss.get("provider_backed_acceptance_done") is False
            and no_loss.get("browser_performance_trace_done") is False
            and int(no_loss.get("production_blocker_count") or 0) > 0
            and all(_dict(no_loss_rows.get(key)).get("blocks_production_replacement") is True for key in REQUIRED_NO_FEATURE_LOSS_GAPS)
            and _flag_false(no_loss, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and no_loss.get("candidate_is_not_buy_instruction") is True,
            "No-feature-loss QA is visible locally, but production radar replacement and legacy retirement must stay blocked.",
        ),
        _row(
            "replacement_gap_triage_blocks_legacy_retirement",
            triage.get("schema_version") == "candidate_radar_replacement_gap_triage.v1"
            and triage.get("status") == "replacement_gap_triage_local_ready_legacy_retirement_blocked"
            and triage.get("local_triage_ready") is True
            and triage.get("legacy_retirement_ready") is False
            and triage.get("production_radar_replacement_complete") is False
            and triage.get("legacy_fallback_required") is True
            and int(triage.get("blocking_gap_count") or 0) > 0
            and all(_dict(triage_rows.get(key)).get("blocks_legacy_retirement") is True for key in REQUIRED_REPLACEMENT_GAPS)
            and _flag_false(triage, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Replacement-gap triage must keep legacy radar retirement blocked until browser/performance/full/deep/provider gaps are resolved.",
        ),
        _row(
            "promotion_blocker_audit_keeps_replacement_pending",
            promotion_audit.get("schema_version") == "candidate_radar_promotion_blocker_audit.v1"
            and promotion_audit.get("status") == "candidate_radar_promotion_blocked"
            and promotion_audit.get("scope") == "local_candidate_radar_promotion_audit_not_production_execution"
            and promotion_audit.get("local_promotion_audit_ready") is True
            and promotion_audit.get("promotion_ready") is False
            and promotion_audit.get("production_radar_replacement_complete") is False
            and promotion_audit.get("legacy_retirement_ready") is False
            and promotion_audit.get("full_pool_scan_done") is False
            and promotion_audit.get("deep_scan_done") is False
            and promotion_audit.get("provider_backed_acceptance_done") is False
            and int(promotion_audit.get("blocking_promotion_count") or 0) > 0
            and int(promotion_audit.get("provider_acceptance_blocker_count") or 0) > 0
            and int(promotion_audit.get("worker_execution_blocker_count") or 0) > 0
            and int(promotion_audit.get("browser_evidence_blocker_count") or 0) >= 0
            and all(key in promotion_rows for key in REQUIRED_PROMOTION_ROWS)
            and all(_dict(promotion_rows.get(key)).get("blocks_promotion") is True for key in REQUIRED_PROMOTION_BLOCKERS)
            and (
                _dict(promotion_rows.get("browser_visual_and_performance_reviewed")).get("status") == "passed"
                and _dict(promotion_rows.get("browser_visual_and_performance_reviewed")).get("blocks_promotion") is False
                and int(promotion_audit.get("browser_evidence_blocker_count") or 0) == 0
                or _dict(promotion_rows.get("browser_visual_and_performance_reviewed")).get("blocks_promotion") is True
                and int(promotion_audit.get("browser_evidence_blocker_count") or 0) > 0
            )
            and policy.get("candidate_radar_promotion_audit_is_local") is True
            and policy.get("candidate_radar_promotion_audit_is_not_production_replacement") is True
            and policy.get("candidate_radar_promotion_requires_provider_worker_browser_evidence") is True
            and _flag_false(promotion_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and promotion_audit.get("does_not_execute_trades") is True
            and promotion_audit.get("does_not_modify_strategy_action") is True
            and promotion_audit.get("candidate_is_not_buy_instruction") is True
            and "candidate_radar_promotion_blocker_audit" in candidate_frontend
            and "candidate_radar_promotion_blocker_rows" in candidate_frontend,
            "Promotion blocker audit must keep Candidate Radar production replacement blocked until provider, worker, browser QA, freshness, and legacy retirement evidence are real.",
        ),
        _row(
            "quick_scan_receipt_is_local_visible_not_replacement",
            quick_receipt.get("schema_version") == "candidate_radar_quick_scan_receipt.v1"
            and quick_receipt.get("status") == "quick_scan_receipt_ready_local_only"
            and quick_receipt.get("scope") == "local_candidate_radar_quick_scan_receipt_not_production_replacement"
            and quick_receipt.get("local_quick_scan_receipt_ready") is True
            and quick_receipt.get("production_radar_replacement_complete") is False
            and quick_receipt.get("legacy_retirement_ready") is False
            and quick_receipt.get("legacy_fallback_required") is True
            and quick_receipt.get("full_pool_scan_done") is False
            and quick_receipt.get("deep_scan_done") is False
            and quick_receipt.get("provider_backed_acceptance_done") is False
            and quick_receipt.get("browser_performance_trace_done") is False
            and quick_receipt.get("browser_visual_delta_qa_done") is False
            and int(quick_receipt.get("row_count") or 0) >= 10
            and int(quick_receipt.get("production_blocker_count") or 0) > 0
            and all(
                _dict(quick_receipt_rows.get(key)).get("local_contract_passed") is True
                for key in {
                    "scan_mode_visible",
                    "candidate_count_visible",
                    "runtime_budget_visible",
                    "provider_gap_visible",
                    "full_deep_provider_blockers_visible",
                    "trade_action_isolation",
                }
            )
            and _dict(quick_receipt_rows.get("full_deep_provider_blockers_visible")).get("production_blocker") is True
            and policy.get("quick_scan_receipt_contract_is_local") is True
            and policy.get("quick_scan_receipt_is_not_production_replacement") is True
            and policy.get("quick_scan_receipt_requires_full_deep_provider_browser_evidence") is True
            and _flag_false(quick_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and quick_receipt.get("does_not_execute_trades") is True
            and quick_receipt.get("does_not_modify_strategy_action") is True
            and quick_receipt.get("candidate_is_not_buy_instruction") is True
            and "quick_scan_execution_receipt" in candidate_frontend
            and "quick_scan_execution_receipt_rows" in candidate_frontend
            and "快扫执行回执" in candidate_frontend,
            "Quick-scan receipt must make local scan coverage, limits, gaps, and production blockers visible without becoming production replacement evidence.",
        ),
        _row(
            "legacy_parity_acceptance_receipt_blocks_feature_loss",
            legacy_parity_acceptance.get("schema_version") == "candidate_radar_legacy_parity_acceptance_receipt.v1"
            and legacy_parity_acceptance.get("status") == "legacy_parity_acceptance_local_ready_production_pending"
            and legacy_parity_acceptance.get("scope")
            == "local_legacy_radar_parity_acceptance_not_production_replacement"
            and legacy_parity_acceptance.get("local_acceptance_receipt_ready") is True
            and legacy_parity_acceptance.get("production_radar_replacement_complete") is False
            and legacy_parity_acceptance.get("legacy_retirement_ready") is False
            and legacy_parity_acceptance.get("legacy_fallback_required") is True
            and legacy_parity_acceptance.get("full_pool_scan_done") is False
            and legacy_parity_acceptance.get("deep_scan_done") is False
            and legacy_parity_acceptance.get("provider_backed_acceptance_done") is False
            and legacy_parity_acceptance.get("browser_visual_qa_done") is False
            and legacy_parity_acceptance.get("browser_performance_trace_done") is False
            and int(legacy_parity_acceptance.get("receipt_row_count") or 0) >= len(REQUIRED_PARITY_ACCEPTANCE_ITEMS)
            and int(legacy_parity_acceptance.get("production_blocker_count") or 0) > 0
            and REQUIRED_PARITY_ACCEPTANCE_ITEMS.issubset(set(legacy_parity_acceptance.get("required_before_legacy_retirement") or []))
            and "treat_gap_reported_as_feature_parity_complete"
            in _list(legacy_parity_acceptance.get("not_allowed_next_steps"))
            and "retire_streamlit_radar_before_provider_worker_browser_acceptance"
            in _list(legacy_parity_acceptance.get("not_allowed_next_steps"))
            and all(_dict(legacy_parity_acceptance_rows.get(key)).get("local_contract_passed") is True for key in REQUIRED_PARITY_ACCEPTANCE_ITEMS)
            and any(
                _dict(legacy_parity_acceptance_rows.get(key)).get("blocks_production_replacement") is True
                for key in REQUIRED_PARITY_ACCEPTANCE_ITEMS
            )
            and _flag_false(legacy_parity_acceptance, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and legacy_parity_acceptance.get("does_not_execute_trades") is True
            and legacy_parity_acceptance.get("does_not_modify_strategy_action") is True
            and legacy_parity_acceptance.get("candidate_is_not_buy_instruction") is True
            and legacy_parity_acceptance.get("contains_secret") is False
            and policy.get("legacy_parity_acceptance_receipt_is_local") is True
            and policy.get("legacy_parity_acceptance_is_not_production_replacement") is True
            and policy.get("legacy_parity_acceptance_requires_provider_worker_browser_evidence") is True
            and "legacy_parity_acceptance_receipt" in candidate_frontend
            and "legacy_parity_acceptance_rows" in candidate_frontend
            and "旧雷达 parity 验收收据" in candidate_frontend,
            "Legacy parity acceptance receipt must turn old radar features into explicit acceptance rows and keep Streamlit fallback/production replacement blocked while gaps remain.",
        ),
        _row(
            "activation_receipt_guides_next_safe_step",
            activation_receipt.get("schema_version") == "candidate_radar_production_activation_receipt.v1"
            and activation_receipt.get("status") == "candidate_radar_activation_receipt_ready_production_blocked"
            and activation_receipt.get("scope") == "local_candidate_radar_activation_receipt_no_execution_or_provider_call"
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("production_radar_replacement_complete") is False
            and activation_receipt.get("legacy_retirement_ready") is False
            and activation_receipt.get("full_pool_scan_done") is False
            and activation_receipt.get("deep_scan_done") is False
            and activation_receipt.get("provider_backed_acceptance_done") is False
            and activation_receipt.get("durable_ci_evidence_complete") is False
            and activation_receipt.get("candidate_is_not_buy_instruction") is True
            and activation_receipt.get("allowed_next_step")
            == "explicit_worker_full_pool_and_deep_scan_acceptance_then_provider_backed_parity_and_browser_review"
            and int(activation_receipt.get("production_blocker_count") or 0) >= len(REQUIRED_ACTIVATION_BLOCKERS)
            and REQUIRED_ACTIVATION_BLOCKERS.issubset(set(activation_receipt.get("production_blockers") or []))
            and all(_dict(activation_rows.get(key)).get("production_blocker") is True for key in REQUIRED_ACTIVATION_BLOCKERS)
            and _flag_false(activation_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and policy.get("candidate_radar_activation_receipt_is_local") is True
            and policy.get("candidate_radar_activation_receipt_is_not_production_replacement") is True
            and policy.get("candidate_radar_activation_requires_worker_provider_browser_evidence") is True
            and any(
                _dict(row).get("api") == "local_candidate_radar_production_activation_receipt"
                for row in _list(cache_packet.get("call_ledger"))
            )
            and "candidate_radar_production_activation_receipt" in candidate_frontend
            and "candidate_radar_production_activation_rows" in candidate_frontend
            and "雷达生产化激活收据" in candidate_frontend,
            "Activation receipt must point to the next safe worker/provider/browser acceptance step while keeping production replacement, legacy retirement, external calls, and buy-signal claims blocked.",
        ),
        _row(
            "result_delta_clarity_is_local_not_visual_qa",
            result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1"
            and result_delta.get("local_result_delta_clarity_ready") is True
            and result_delta.get("production_radar_replacement_complete") is False
            and result_delta.get("browser_visual_delta_qa_done") is False
            and _flag_false(result_delta, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and result_delta.get("does_not_execute_trades") is True
            and result_delta.get("does_not_modify_strategy_action") is True,
            "Result-delta clarity may be locally ready; browser visual delta QA and production replacement must remain pending.",
        ),
        _row(
            "priority_explanation_is_local_not_trade_signal",
            priority_explanation.get("schema_version") == "candidate_radar_priority_explanation.v1"
            and priority_explanation.get("scope") == "local_cache_rank_explanation_not_rescore_or_trade_signal"
            and priority_explanation.get("status")
            in {"candidate_priority_explanation_ready", "candidate_priority_explanation_empty"}
            and priority_explanation.get("cached_rank_preserved") is True
            and priority_explanation.get("cached_score_preserved") is True
            and priority_explanation.get("uses_existing_rank_only") is True
            and priority_explanation.get("uses_existing_score_only") is True
            and priority_explanation.get("does_not_recompute_score") is True
            and priority_explanation.get("does_not_sort_candidates") is True
            and priority_explanation.get("does_not_calculate_action") is True
            and priority_explanation.get("priority_explanation_is_not_trade_signal") is True
            and priority_explanation.get("production_radar_replacement_complete") is False
            and policy.get("candidate_priority_explanation_contract_is_local") is True
            and policy.get("candidate_priority_explanation_uses_existing_rank_only") is True
            and policy.get("candidate_priority_explanation_uses_existing_score_only") is True
            and policy.get("candidate_priority_explanation_is_not_trade_signal") is True
            and _flag_false(priority_explanation, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and priority_explanation.get("does_not_execute_trades") is True
            and priority_explanation.get("does_not_modify_strategy_action") is True,
            "Candidate priority explanations must only explain existing cache rank/score; they must not rescore, reorder, call providers, or become trade signals.",
        ),
        _row(
            "full_pool_plan_is_plan_only",
            full_pool_plan.get("schema_version") == "candidate_radar_full_pool_plan.v1"
            and full_pool_plan.get("status") == "full_pool_plan_ready"
            and full_pool_plan.get("full_pool_scan_done") is False
            and full_pool_plan.get("full_pool_validation_done") is False
            and full_pool_plan.get("worker_task_required") is True
            and full_pool_plan.get("page_render_starts_full_pool") is False
            and full_pool_plan.get("cache_get_starts_full_pool") is False
            and full_pool_plan.get("provider_refresh_executed") is False
            and full_pool_plan.get("candidate_scoring_executed") is False
            and full_pool_plan.get("candidate_packet_written_by_plan") is False
            and _flag_false(full_pool_plan, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and full_pool_plan.get("candidate_is_not_buy_instruction") is True,
            "Full-pool plan must remain plan-only: no market scan, provider refresh, candidate scoring, or packet write.",
        ),
        _row(
            "deep_scan_plan_is_plan_only",
            deep_scan_plan.get("schema_version") == "candidate_radar_deep_scan_plan.v1"
            and deep_scan_plan.get("status") == "deep_scan_plan_ready"
            and deep_scan_plan.get("deep_scan_done") is False
            and deep_scan_plan.get("deep_scan_validation_done") is False
            and deep_scan_plan.get("page_render_starts_deep_scan") is False
            and deep_scan_plan.get("cache_get_starts_deep_scan") is False
            and deep_scan_plan.get("provider_refresh_executed") is False
            and deep_scan_plan.get("candidate_scoring_executed") is False
            and deep_scan_plan.get("candidate_packet_written_by_plan") is False
            and _flag_false(deep_scan_plan, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and deep_scan_plan.get("candidate_is_not_buy_instruction") is True,
            "Deep-scan plan must remain plan-only: no deep scan execution, provider refresh, DeepSeek call, scoring, or trade instruction.",
        ),
        _row(
            "candidate_browser_qa_runbook_is_local_execution_pending",
            _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("schema_version")
            == "candidate_radar_browser_qa_runbook.v1"
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("status")
            == "candidate_radar_browser_qa_runbook_ready_execution_pending"
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("local_runbook_ready") is True
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("visual_qa_complete") is False
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("browser_performance_trace_done") is False
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("production_radar_replacement_complete") is False
            and _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("legacy_retirement_ready") is False
            and len(_list(cache_packet.get("candidate_browser_qa_matrix_rows"))) == 4
            and "candidate_radar_browser_qa_runbook.v1" in browser_qa_runbook
            and "local_candidate_radar_browser_qa_runbook_not_browser_execution" in browser_qa_runbook
            and "#candidates" in browser_qa_runbook
            and "opens_no_browser" in browser_qa_runbook
            and "writes_no_artifacts" in browser_qa_runbook
            and "command_center_3_motion_browser_qa_result.v1" in motion_runner
            and "#candidates" in motion_runner
            and "radar-result-cluster" in candidate_frontend
            and "candidate_browser_qa_runbook_contract" in candidate_frontend
            and ("request" + "s") not in browser_qa_runbook
            and ("ht" + "tpx") not in browser_qa_runbook
            and ("api.github" + ".com") not in browser_qa_runbook,
            "Candidate Radar browser QA runbook must stay local/static and keep visual/performance QA pending until an explicit browser pass.",
        ),
        _row(
            "candidate_browser_qa_evidence_reader_is_local_artifact_only",
            browser_qa_evidence.get("schema_version") == "candidate_radar_browser_qa_evidence.v1"
            and browser_qa_evidence.get("scope") == "local_candidate_radar_browser_qa_evidence_reader_no_browser_execution"
            and browser_qa_evidence.get("candidate_route") == "#candidates"
            and browser_qa_evidence.get("opens_no_browser") is True
            and browser_qa_evidence.get("starts_no_servers") is True
            and browser_qa_evidence.get("writes_no_artifacts") is True
            and browser_qa_evidence.get("reads_ignored_local_reports_only") is True
            and browser_qa_evidence.get("production_radar_replacement_complete") is False
            and browser_qa_evidence.get("legacy_retirement_ready") is False
            and _flag_false(browser_qa_evidence, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and browser_qa_evidence.get("does_not_execute_trades") is True
            and browser_qa_evidence.get("does_not_modify_strategy_action") is True
            and browser_qa_evidence.get("candidate_is_not_buy_instruction") is True
            and policy.get("candidate_browser_qa_evidence_reads_local_artifact_only") is True
            and policy.get("candidate_browser_qa_evidence_does_not_open_browser") is True
            and policy.get("candidate_browser_qa_evidence_does_not_write_artifacts") is True
            and policy.get("candidate_browser_qa_evidence_is_not_production_replacement") is True
            and "candidate_browser_qa_evidence_summary" in candidate_frontend
            and "candidate_browser_qa_evidence_rows" in candidate_frontend,
            "Candidate Radar browser QA evidence may read ignored local reports for #candidates, but it must not open a browser, write artifacts, call providers, or mark production replacement complete.",
        ),
        _row(
            "candidate_browser_qa_review_is_button_gated_not_production",
            browser_qa_review.get("schema_version") == "candidate_radar_browser_qa_review.v1"
            and browser_qa_review.get("scope") == "button_gated_local_candidate_browser_qa_review_no_browser_execution"
            and browser_qa_review.get("opens_no_browser") is True
            and browser_qa_review.get("starts_no_servers") is True
            and browser_qa_review.get("writes_no_artifacts") is True
            and browser_qa_review.get("reads_ignored_local_reports_only") is True
            and browser_qa_review.get("production_radar_replacement_complete") is False
            and browser_qa_review.get("legacy_retirement_ready") is False
            and browser_qa_review.get("full_pool_scan_done") is False
            and browser_qa_review.get("deep_scan_done") is False
            and browser_qa_review.get("provider_backed_acceptance_done") is False
            and _flag_false(browser_qa_review, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and browser_qa_review.get("does_not_execute_trades") is True
            and browser_qa_review.get("does_not_modify_strategy_action") is True
            and policy.get("candidate_browser_qa_review_is_button_gated") is True
            and policy.get("candidate_browser_qa_review_does_not_open_browser") is True
            and policy.get("candidate_browser_qa_review_is_not_production_replacement") is True
            and "postCandidateRadarBrowserQaReview" in candidate_frontend
            and "candidate_browser_qa_review_contract" in candidate_frontend,
            "Candidate Radar browser QA review must be POST/button-gated and must not execute browser QA or complete production radar replacement.",
        ),
        _row(
            "plan_packet_preserves_pending_boundaries",
            _dict(plan_packet.get("full_pool_scan_plan")).get("full_pool_scan_done") is False
            and _dict(plan_packet.get("deep_scan_plan")).get("deep_scan_done") is False
            and _dict(plan_packet.get("no_feature_loss_acceptance_contract")).get("production_radar_replacement_complete") is False
            and _dict(plan_packet.get("replacement_gap_triage_contract")).get("legacy_retirement_ready") is False
            and _dict(plan_packet.get("result_delta_clarity_contract")).get("production_radar_replacement_complete") is False
            and _flag_false(plan_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and plan_packet.get("does_not_execute_trades") is True
            and plan_packet.get("does_not_modify_strategy_action") is True,
            "A locally built plan packet must keep full/deep execution, production replacement, and legacy retirement pending.",
        ),
        _row(
            "push_gate_runs_contract_after_factor",
            "scripts/candidate_radar_contract.py" in push_gate_script
            and CANDIDATE_BROWSER_QA_RUNBOOK_PATH in push_gate_script
            and "Candidate Radar contract" in push_gate_script
            and "Candidate Radar browser QA runbook" in push_gate_script
            and "candidate_radar_contract: passed_local_contract_replacement_pending" in push_gate_script
            and push_gate_script.find('run_step "Factor Test Lab contract"') < push_gate_script.find('run_step "Candidate Radar contract"')
            and push_gate_script.find('run_step "Candidate Radar contract"') < push_gate_script.find('run_step "Candidate Radar browser QA runbook"')
            and push_gate_script.find('run_step "Candidate Radar browser QA runbook"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run the LTG-13 local contract and browser QA runbook before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_candidate_radar_contract.v1" in this_script
            and "local_candidate_radar_contract_no_provider_execution" in this_script
            and "production_radar_replacement_complete" in this_script
            and "legacy_retirement_ready" in this_script
            and "candidate_radar_quick_scan_receipt.v1" in this_script
            and "candidate_radar_full_pool_local_execution_receipt.v1" in this_script
            and "candidate_radar_deep_scan_local_review_receipt.v1" in this_script
            and "candidate_radar_search_quant_projection_receipt.v1" in this_script
            and "candidate_radar_production_activation_receipt.v1" in this_script
            and "candidate_is_not_buy_instruction" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_candidate_radar_contract.v1",
        "status": "candidate_radar_contract_passed" if not blockers else "candidate_radar_contract_blocked",
        "scope": "local_candidate_radar_contract_no_provider_execution",
        "ltg": "LTG-13/LTG-11",
        "contract_ready": not blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "candidate_browser_qa_runbook_ready": _dict(cache_packet.get("candidate_browser_qa_runbook_contract")).get("local_runbook_ready") is True,
        "candidate_browser_qa_evidence_found": browser_qa_evidence.get("local_browser_qa_evidence_found") is True,
        "candidate_browser_qa_review_ready": browser_qa_review.get("local_browser_qa_review_ready") is True,
        "candidate_radar_activation_receipt_ready": activation_receipt.get("local_activation_receipt_ready") is True,
        "legacy_parity_acceptance_receipt_ready": legacy_parity_acceptance.get("local_acceptance_receipt_ready") is True,
        "full_pool_local_execution_receipt_ready": full_pool_local_receipt.get("local_full_pool_execution_done") is True,
        "deep_scan_local_review_receipt_ready": deep_scan_local_receipt.get("local_deep_scan_review_done") is True,
        "search_quant_projection_receipt_ready": search_quant_projection_receipt.get("local_receipt_ready") is True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "cache_status": cache_packet.get("status"),
            "cache_scan_mode": cache_packet.get("scan_mode"),
            "candidate_count": _dict(cache_packet.get("counts")).get("candidate_count"),
            "fast_scan_readiness_status": readiness.get("status"),
            "no_feature_loss_status": no_loss.get("status"),
            "no_feature_loss_production_blocker_count": no_loss.get("production_blocker_count"),
            "replacement_gap_status": triage.get("status"),
            "replacement_gap_blocking_count": triage.get("blocking_gap_count"),
            "promotion_audit_status": promotion_audit.get("status"),
            "promotion_blocking_count": promotion_audit.get("blocking_promotion_count"),
            "quick_scan_receipt_status": quick_receipt.get("status"),
            "quick_scan_receipt_production_blocker_count": quick_receipt.get("production_blocker_count"),
            "legacy_parity_acceptance_status": legacy_parity_acceptance.get("status"),
            "legacy_parity_acceptance_production_blocker_count": legacy_parity_acceptance.get("production_blocker_count"),
            "full_pool_local_execution_status": full_pool_local_receipt.get("status"),
            "full_pool_local_execution_candidate_count": full_pool_local_receipt.get("normalized_candidate_count"),
            "full_pool_local_execution_production_blocker_count": full_pool_local_receipt.get("production_blocker_count"),
            "deep_scan_local_review_status": deep_scan_local_receipt.get("status"),
            "deep_scan_local_review_candidate_count": deep_scan_local_receipt.get("reviewed_candidate_count"),
            "deep_scan_local_review_production_blocker_count": deep_scan_local_receipt.get("production_blocker_count"),
            "activation_receipt_status": activation_receipt.get("status"),
            "activation_receipt_production_blocker_count": activation_receipt.get("production_blocker_count"),
            "activation_receipt_pending_evidence_count": activation_receipt.get("pending_evidence_count"),
            "result_delta_status": result_delta.get("status"),
            "priority_explanation_status": priority_explanation.get("status"),
            "priority_explanation_gap_count": priority_explanation.get("explanation_gap_count"),
            "candidate_browser_qa_evidence_status": browser_qa_evidence.get("status"),
            "candidate_browser_qa_evidence_row_count": browser_qa_evidence.get("row_count"),
            "candidate_browser_qa_evidence_review_required_count": browser_qa_evidence.get("review_required_count"),
            "candidate_browser_qa_review_status": browser_qa_review.get("status"),
            "candidate_browser_qa_review_blocking_count": browser_qa_review.get("blocking_review_count"),
            "full_pool_plan_blocker_count": full_pool_plan.get("blocking_issue_count"),
            "deep_scan_plan_blocker_count": deep_scan_plan.get("blocking_issue_count"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Full-pool execution, deep-scan execution, provider-backed parity acceptance, browser performance/visual QA, and legacy radar retirement remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-13 Candidate Radar contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"candidate_radar_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "production_radar_replacement_complete: false; legacy_retirement_ready: false".format(
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
