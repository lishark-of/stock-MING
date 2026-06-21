#!/usr/bin/env python3
"""Validate the local LTG-07 DeepSeek governance contract.

This push-gate guard never calls a model. It keeps manual explanation,
sanitizer, JSON-stability audit, response-format review, token-budget display,
button gating, and default-off automation separate from production DeepSeek
automatic explanation readiness.
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


REQUIRED_ALLOWED_KEYS = {
    "summary",
    "support_notes",
    "suppress_notes",
    "conflict_notes",
    "missing_data_notes",
    "discipline_notes",
}
REQUIRED_JSON_BLOCKERS = {
    "json_success_rate_threshold",
    "larger_benchmark_done",
    "response_format_enforced",
}
REQUIRED_RESPONSE_FORMAT_BLOCKERS = {
    "provider_response_format_enforced",
    "retry_repair_policy_ready",
    "larger_benchmark_required",
}
REQUIRED_JSON_ROWS = {
    "allowed_top_level_schema",
    "illegal_fields_discarded",
    "parse_failed_does_not_pollute_packet",
    "numeric_and_action_overwrite_blocked",
    "token_budget_estimate_present",
    "model_call_not_triggered_by_audit",
    "cache_and_render_never_call_model",
    "auto_after_task_default_off",
    "json_success_rate_threshold",
    "larger_benchmark_done",
    "response_format_enforced",
}
REQUIRED_RESPONSE_FORMAT_ROWS = {
    "json_object_instruction_present",
    "allowed_top_level_keys_exact",
    "provider_response_format_enforced",
    "retry_repair_policy_ready",
    "parse_failed_discard_policy",
    "illegal_fields_sanitized",
    "numeric_and_action_overwrite_blocked",
    "token_budget_visible",
    "cache_render_no_model_call",
    "auto_after_task_default_off",
    "larger_benchmark_required",
}
REQUIRED_RETRY_REPAIR_PATHS = {
    "direct_json",
    "fenced_json_extraction",
    "embedded_json_extraction",
    "sanitize_illegal_fields",
    "parse_failed_discard",
}
REQUIRED_DEEPSEEK_PRODUCTION_STAGES = {
    "larger_provider_benchmark",
    "provider_response_format_enforcement",
    "bounded_retry_repair_execution",
    "token_budget_cost_evidence",
    "auto_after_task_mode_gate",
    "model_ledger_hash_dedupe",
    "sanitizer_parse_failed_discard",
    "production_promotion_review",
}
REQUIRED_BENCHMARK_RECIPE_PHASES = {
    "explicit_user_approval",
    "server_secret_preflight",
    "benchmark_sample_set",
    "provider_response_format",
    "bounded_retry_repair",
    "model_call_ledger",
    "sanitizer_parse_review",
    "token_budget_cost_review",
    "auto_after_task_mode_gate",
    "production_promotion_review",
}
REQUIRED_DURABLE_EVIDENCE_KEYS = (
    "manual_default_off_governance_visible",
    "sanitizer_whitelist_visible",
    "json_stability_audit_visible",
    "response_format_review_visible",
    "retry_repair_dry_run_visible",
    "production_activation_receipt_visible",
    "provider_benchmark_execution_recipe_visible",
    "provider_benchmark_report_required",
    "provider_response_format_execution_required",
    "bounded_retry_repair_execution_required",
    "model_ledger_hash_dedupe_required",
    "sanitizer_parse_failed_provider_review_required",
    "token_budget_cost_evidence_required",
    "auto_after_task_mode_gate_required",
    "redaction_review_required",
    "production_promotion_review_required",
    "no_model_trade_action_secret_boundary",
)
REQUIRED_DURABLE_EVIDENCE_MISSING_KEYS = (
    "provider_benchmark_report_required",
    "provider_response_format_execution_required",
    "bounded_retry_repair_execution_required",
    "model_ledger_hash_dedupe_required",
    "sanitizer_parse_failed_provider_review_required",
    "token_budget_cost_evidence_required",
    "auto_after_task_mode_gate_required",
    "redaction_review_required",
    "production_promotion_review_required",
)
DEEPSEEK_PRODUCTION_STAGE_LABELS = {
    "larger_provider_benchmark": "larger provider-backed JSON stability benchmark",
    "provider_response_format_enforcement": "provider response_format enforcement",
    "bounded_retry_repair_execution": "bounded retry/repair provider execution",
    "token_budget_cost_evidence": "token budget and cost evidence",
    "auto_after_task_mode_gate": "auto_after_task explicit mode gate",
    "model_ledger_hash_dedupe": "model ledger, input/output hash, and dedupe",
    "sanitizer_parse_failed_discard": "sanitizer and parse-failed discard evidence",
    "production_promotion_review": "production promotion review",
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


def _rows_by_criterion(rows: Any) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("criterion") or ""): row
        for row in _list(rows)
        if isinstance(row, dict)
    }


def _deepseek_task(catalog: dict[str, Any]) -> dict[str, Any]:
    for task in _list(catalog.get("tasks")):
        if isinstance(task, dict) and task.get("task_type") == "run_deepseek_factor_explanation":
            return task
    return {}


def _deepseek_scope_ticket_task(catalog: dict[str, Any]) -> dict[str, Any]:
    for task in _list(catalog.get("tasks")):
        if isinstance(task, dict) and task.get("task_type") == "run_deepseek_provider_benchmark_scope_ticket":
            return task
    return {}


def _local_prompt_preview() -> dict[str, Any]:
    return {
        "input_hash": "local-deepseek-governance-contract",
        "json_object_instruction_present": True,
        "allowed_top_level_keys": sorted(REQUIRED_ALLOWED_KEYS),
        "token_estimate": 320,
        "user_prompt": "Return one JSON object with only the allowed explanation fields.",
    }


def _local_validation_summary(sanitized: dict[str, Any], prompt_preview: dict[str, Any]) -> dict[str, Any]:
    ignored = _list(sanitized.get("ignored_keys"))
    return {
        "status": sanitized.get("status") or "success",
        "validation_mode": "local_sanitizer_only",
        "model_call_status": "not_called",
        "input_hash": prompt_preview.get("input_hash"),
        "output_hash": sanitized.get("output_hash") or "",
        "prompt_token_estimate": prompt_preview.get("token_estimate") or 0,
        "output_token_estimate": sanitized.get("token_estimate") or 0,
        "parse_failed": bool(sanitized.get("parse_failed")),
        "allowed_top_level_keys": prompt_preview.get("allowed_top_level_keys") or [],
        "ignored_key_count": len(ignored),
        "ignored_keys": sorted(str(key) for key in ignored),
        "invalid_output_discarded": bool(sanitized.get("parse_failed")),
        "does_not_override_numeric_values": sanitized.get("does_not_override_numeric_values") is not False,
        "does_not_output_strategy_action": sanitized.get("does_not_output_strategy_action") is not False,
        "does_not_modify_strategy_action": True,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
    }


def _deepseek_production_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key in sorted(REQUIRED_DEEPSEEK_PRODUCTION_STAGES):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": DEEPSEEK_PRODUCTION_STAGE_LABELS[stage_key],
                "scope": "deepseek_production_stage_scope_manifest",
                "current_status": "local_governance_or_dry_run_only",
                "target_status": "provider_benchmark_or_runtime_evidence_required",
                "required_before_production": True,
                "provider_benchmark_done": False,
                "response_format_enforced": False,
                "bounded_retry_repair_executed": False,
                "token_budget_cost_evidence_complete": False,
                "auto_after_task_production_ready": False,
                "model_execution_implemented": False,
                "production_deepseek_explanation_complete": False,
                "deepseek_called_by_contract": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": [
                    "provider-backed benchmark sample",
                    "provider response_format proof",
                    "bounded retry/repair execution ledger",
                    "token budget and cost ledger",
                    "explicit production promotion review",
                ],
            }
        )
    return rows


def build_contract() -> dict[str, Any]:
    cache_packet = factor_service.read_factor_quant_cache()
    governance = _dict(cache_packet.get("deepseek_explain_governance"))
    validation = _dict(cache_packet.get("deepseek_validation_summary"))
    json_audit = _dict(cache_packet.get("deepseek_json_stability_audit"))
    json_rows = _rows_by_criterion(cache_packet.get("deepseek_json_stability_rows") or json_audit.get("rows"))
    response_review = _dict(cache_packet.get("deepseek_response_format_review_contract"))
    response_rows = _rows_by_criterion(
        cache_packet.get("deepseek_response_format_review_rows") or response_review.get("rows")
    )
    retry_repair_dry_run = _dict(cache_packet.get("deepseek_retry_repair_dry_run_contract"))
    retry_repair_rows = [
        row for row in _list(cache_packet.get("deepseek_retry_repair_dry_run_rows") or retry_repair_dry_run.get("rows"))
        if isinstance(row, dict)
    ]
    activation_receipt = _dict(cache_packet.get("deepseek_production_activation_receipt"))
    activation_rows = _rows_by_criterion(
        cache_packet.get("deepseek_production_activation_rows") or activation_receipt.get("rows")
    )
    benchmark_recipe = _dict(cache_packet.get("deepseek_provider_benchmark_execution_recipe"))
    benchmark_recipe_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(cache_packet.get("deepseek_provider_benchmark_execution_rows") or benchmark_recipe.get("rows"))
        if isinstance(row, dict)
    }
    benchmark_scope_ticket = _dict(cache_packet.get("deepseek_provider_benchmark_scope_ticket_receipt"))
    benchmark_scope_ticket_rows = _rows_by_criterion(
        cache_packet.get("deepseek_provider_benchmark_scope_ticket_rows") or benchmark_scope_ticket.get("rows")
    )
    durable_recipe = _dict(cache_packet.get("deepseek_durable_evidence_recipe"))
    durable_recipe_rows = [
        row for row in _list(cache_packet.get("deepseek_durable_evidence_rows") or durable_recipe.get("rows"))
        if isinstance(row, dict)
    ]
    durable_evidence_keys = {str(row.get("evidence_key") or "") for row in durable_recipe_rows}
    catalog = task_service.build_task_catalog()
    task = _deepseek_task(catalog)
    scope_ticket_task = _deepseek_scope_ticket_task(catalog)
    task_strategy = _dict(task.get("deepseek_model_strategy"))

    sample_payload = {
        "summary": "只解释因子，不生成交易动作。",
        "support_notes": ["支持项"],
        "suppress_notes": ["压制项"],
        "conflict_notes": ["冲突项"],
        "missing_data_notes": ["缺口项"],
        "discipline_notes": ["纪律项"],
        "strategy_action": "buy",
        "price": 99.9,
        "factor_values": {"momentum": 1.2},
        "operation_zones": ["danger"],
        "position": "full",
    }
    sanitized = factor_research.sanitize_factor_deepseek_explanation(
        sample_payload,
        model_used=str(governance.get("model") or ""),
        input_hash="local-deepseek-governance-contract",
    )
    malformed = factor_research.sanitize_factor_deepseek_explanation(
        "not json and not useful",
        model_used=str(governance.get("model") or ""),
        input_hash="local-parse-failed-contract",
    )
    prompt_preview = _local_prompt_preview()
    local_validation = _local_validation_summary(sanitized, prompt_preview)
    local_json_audit = factor_research.build_factor_deepseek_json_stability_audit(
        prompt_preview=prompt_preview,
        validation_summary=local_validation,
        governance=governance,
    )
    local_response_review = factor_research.build_factor_deepseek_response_format_review_contract(
        prompt_preview=prompt_preview,
        validation_summary=local_validation,
        governance=governance,
        json_stability_audit=local_json_audit,
    )
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/deepseek_governance_contract.py")
    deepseek_production_stage_scope_rows = _deepseek_production_stage_scope_rows()

    rows = [
        _row(
            "cache_get_governance_is_manual_default_no_model_call",
            governance.get("mode") in {"manual_only", "disabled"}
            and governance.get("manual_task_allowed") is True
            and governance.get("auto_after_task") is False
            and governance.get("configured_auto_after_task") is False
            and governance.get("cache_reads_never_call_deepseek") is True
            and governance.get("react_render_never_calls_deepseek") is True
            and governance.get("does_not_override_numeric_values") is True
            and governance.get("does_not_modify_strategy_action") is True
            and validation.get("validation_mode") == "local_sanitizer_only"
            and validation.get("model_call_status") == "not_called"
            and _flag_false(validation, "external_calls_triggered", "deepseek_called")
            and _flag_false(cache_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and cache_packet.get("does_not_execute_trades") is True
            and cache_packet.get("does_not_modify_strategy_action") is True,
            "GET factor cache must show manual/default-off DeepSeek governance without model calls, provider calls, trades, or action mutation.",
        ),
        _row(
            "sanitizer_whitelist_discards_action_numeric_fields",
            sanitized.get("status") == "success"
            and sanitized.get("parse_failed") is False
            and set(_dict(sanitized.get("payload")).keys()) == REQUIRED_ALLOWED_KEYS
            and {"strategy_action", "price", "factor_values", "operation_zones", "position"}.issubset(
                set(str(key) for key in _list(sanitized.get("ignored_keys")))
            )
            and sanitized.get("does_not_override_numeric_values") is True
            and sanitized.get("does_not_output_strategy_action") is True
            and sanitized.get("output_hash")
            and int(sanitized.get("token_estimate") or 0) > 0,
            "Sanitizer must keep only six explanation fields and discard action, price, position, factor value, and operation-zone fields.",
        ),
        _row(
            "parse_failed_output_is_discarded_and_hashable",
            malformed.get("status") == "parse_failed"
            and malformed.get("parse_failed") is True
            and set(_dict(malformed.get("payload")).keys()) == REQUIRED_ALLOWED_KEYS
            and malformed.get("does_not_override_numeric_values") is True
            and malformed.get("does_not_output_strategy_action") is True
            and malformed.get("output_hash")
            and int(malformed.get("token_estimate") or 0) > 0,
            "Malformed text must become parse_failed with a whitelisted empty payload, safe hash, token estimate, and no overwrite/action permissions.",
        ),
        _row(
            "json_stability_audit_blocks_production_auto",
            json_audit.get("schema_version") == "factor_deepseek_json_stability_audit.v1"
            and json_audit.get("status") == "manual_ready_production_blocked"
            and json_audit.get("scope") == "local_sanitizer_prompt_contract_not_model_call"
            and json_audit.get("manual_explanation_ready") is True
            and json_audit.get("production_ready") is False
            and json_audit.get("auto_after_task_production_ready") is False
            and float(json_audit.get("last_known_mini_benchmark_success_rate") or 0) < float(
                json_audit.get("required_json_success_rate") or 0.9
            )
            and json_audit.get("larger_benchmark_done") is False
            and json_audit.get("response_format_enforced") is False
            and REQUIRED_JSON_BLOCKERS.issubset(set(_list(json_audit.get("production_blockers"))))
            and REQUIRED_JSON_ROWS.issubset(set(json_rows))
            and json_audit.get("model_call_status") == "not_called"
            and _flag_false(json_audit, "external_calls_triggered", "deepseek_called", "tushare_called", "github_called")
            and json_audit.get("does_not_execute_trades") is True
            and json_audit.get("does_not_modify_strategy_action") is True,
            "JSON stability audit may prove local manual safety, but production automation stays blocked until >90% benchmark, larger sample, and provider response format are proven.",
        ),
        _row(
            "response_format_review_is_local_not_provider_enforcement",
            response_review.get("schema_version") == "factor_deepseek_response_format_review_contract.v1"
            and response_review.get("status") == "response_format_review_ready_provider_enforcement_pending"
            and response_review.get("scope") == "local_response_format_review_no_model_call"
            and response_review.get("local_response_format_review_ready") is True
            and response_review.get("manual_explanation_ready") is True
            and response_review.get("production_ready") is False
            and response_review.get("provider_response_format_enforced") is False
            and response_review.get("retry_repair_policy_ready") is False
            and response_review.get("larger_benchmark_done") is False
            and response_review.get("auto_after_task_production_ready") is False
            and response_review.get("model_call_status") == "not_called"
            and response_review.get("allowed_key_count") == len(REQUIRED_ALLOWED_KEYS)
            and set(_list(response_review.get("allowed_top_level_keys"))) == REQUIRED_ALLOWED_KEYS
            and REQUIRED_RESPONSE_FORMAT_BLOCKERS.issubset(set(_list(response_review.get("production_blockers"))))
            and REQUIRED_RESPONSE_FORMAT_ROWS.issubset(set(response_rows))
            and _flag_false(response_review, "external_calls_triggered", "deepseek_called", "tushare_called", "github_called", "contains_secret")
            and response_review.get("does_not_execute_trades") is True
            and response_review.get("does_not_modify_strategy_action") is True
            and response_review.get("does_not_override_numeric_values") is True
            and response_review.get("does_not_output_strategy_action") is True,
            "Response-format review is a local contract; provider response_format, bounded retry/repair, and larger benchmark remain production blockers.",
        ),
        _row(
            "retry_repair_dry_run_is_local_and_production_blocked",
            retry_repair_dry_run.get("schema_version") == "factor_deepseek_retry_repair_dry_run_contract.v1"
            and retry_repair_dry_run.get("status") == "retry_repair_dry_run_ready_provider_execution_pending"
            and retry_repair_dry_run.get("scope") == "local_retry_repair_dry_run_no_model_call"
            and retry_repair_dry_run.get("local_retry_repair_dry_run_ready") is True
            and retry_repair_dry_run.get("retry_repair_policy_ready") is False
            and retry_repair_dry_run.get("bounded_retry_repair_ready") is False
            and retry_repair_dry_run.get("provider_retry_repair_executed") is False
            and retry_repair_dry_run.get("production_deepseek_explanation_complete") is False
            and int(retry_repair_dry_run.get("case_count") or 0) >= 5
            and int(retry_repair_dry_run.get("passed_case_count") or 0) == int(retry_repair_dry_run.get("case_count") or -1)
            and int(retry_repair_dry_run.get("parse_failed_case_count") or 0) >= 1
            and REQUIRED_RETRY_REPAIR_PATHS.issubset(set(_list(retry_repair_dry_run.get("repair_paths"))))
            and {"provider_retry_repair_execution", "provider_response_format_enforced", "larger_benchmark_required"}.issubset(
                set(_list(retry_repair_dry_run.get("production_blockers")))
            )
            and retry_repair_rows
            and all(row.get("passed") is True for row in retry_repair_rows)
            and all(row.get("model_call_status") == "not_called" for row in retry_repair_rows)
            and all(row.get("does_not_override_numeric_values") is True for row in retry_repair_rows)
            and all(row.get("does_not_output_strategy_action") is True for row in retry_repair_rows)
            and _flag_false(retry_repair_dry_run, "external_calls_triggered", "deepseek_called", "tushare_called", "github_called", "contains_secret")
            and retry_repair_dry_run.get("does_not_execute_trades") is True
            and retry_repair_dry_run.get("does_not_modify_strategy_action") is True,
            "Retry/repair dry-run may prove local extraction, discard, and sanitizer behavior, but provider retry execution and production automation must stay blocked.",
        ),
        _row(
            "local_builders_match_cache_governance_boundaries",
            local_json_audit.get("manual_explanation_ready") is True
            and local_json_audit.get("production_ready") is False
            and local_json_audit.get("model_call_status") == "not_called"
            and REQUIRED_JSON_BLOCKERS.issubset(set(_list(local_json_audit.get("production_blockers"))))
            and local_response_review.get("local_response_format_review_ready") is True
            and local_response_review.get("production_ready") is False
            and local_response_review.get("model_call_status") == "not_called"
            and REQUIRED_RESPONSE_FORMAT_BLOCKERS.issubset(set(_list(local_response_review.get("production_blockers")))),
            "Direct local audit builders must agree with cache governance: manual explanation ready, production automatic explanation blocked, and no model call.",
        ),
        _row(
            "deepseek_task_is_button_gated_and_config_driven",
            task.get("route") == "POST /api/factor-quant/deepseek-explain"
            and task.get("button_gated") is True
            and task.get("current_backend") == "guarded_prompt_or_payload_sanitizer"
            and task.get("external_call_policy") == "governed_manual_or_auto_after_task_deepseek_capable_current_no_model_call"
            and task.get("default_explanation_mode") == "manual_only"
            and task.get("auto_after_task_default") is False
            and task.get("call_ledger_required") is True
            and task.get("same_input_hash_deduplicated") is True
            and task.get("does_not_hardcode_deepseek_model") is True
            and task.get("does_not_execute_trades") is True
            and task.get("does_not_modify_strategy_action") is True
            and task_strategy.get("purpose") == "factor_explain"
            and task_strategy.get("does_not_hardcode_model") is True
            and task_strategy.get("external_call_on_cache_read") is False
            and task_strategy.get("contains_secret") is False,
            "DeepSeek explanation must remain behind explicit POST/task controls, centralized model strategy, call ledger, dedupe, and no-trade/no-action boundaries.",
        ),
        _row(
            "production_activation_receipt_guides_next_safe_step",
            activation_receipt.get("schema_version") == "deepseek_production_activation_receipt.v1"
            and activation_receipt.get("status") == "deepseek_activation_receipt_ready_provider_benchmark_pending"
            and activation_receipt.get("scope") == "local_deepseek_production_activation_receipt_no_model_call"
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("manual_explanation_ready") is True
            and activation_receipt.get("provider_benchmark_done") is False
            and activation_receipt.get("larger_benchmark_done") is False
            and activation_receipt.get("provider_response_format_enforced") is False
            and activation_receipt.get("retry_repair_policy_ready") is False
            and activation_receipt.get("bounded_retry_repair_ready") is False
            and activation_receipt.get("token_budget_cost_evidence_complete") is False
            and activation_receipt.get("auto_after_task_production_ready") is False
            and activation_receipt.get("production_deepseek_explanation_complete") is False
            and activation_receipt.get("provider_model_called_by_receipt") is False
            and activation_receipt.get("cache_get_external_calls") is False
            and activation_receipt.get("receipt_external_calls_triggered") is False
            and _flag_false(activation_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called", "contains_secret")
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and activation_receipt.get("does_not_override_numeric_values") is True
            and activation_receipt.get("does_not_output_strategy_action") is True
            and "explicit_provider_benchmark" in str(activation_receipt.get("allowed_next_step") or "")
            and "sanitizer as provider benchmark" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "auto_after_task default-on promotion" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "provider benchmark JSON success rate > 90%" in _list(activation_receipt.get("missing_evidence"))
            and {"provider_benchmark_required", "provider_response_format_enforcement_required", "bounded_retry_repair_required", "token_budget_cost_evidence_required", "auto_after_task_activation_required"}.issubset(set(activation_rows))
            and activation_rows.get("manual_default_off_governance_ready", {}).get("passed") is True
            and activation_rows.get("provider_benchmark_required", {}).get("passed") is False
            and activation_rows.get("no_get_or_render_model_call_boundary", {}).get("passed") is True,
            "DeepSeek production activation receipt must point to explicit provider benchmark/response-format/retry/cost review while keeping production completion false.",
        ),
        _row(
            "provider_benchmark_execution_recipe_is_local_pending",
            benchmark_recipe.get("schema_version") == "factor_deepseek_provider_benchmark_execution_recipe.v1"
            and benchmark_recipe.get("status") == "deepseek_provider_benchmark_recipe_ready_model_execution_pending"
            and benchmark_recipe.get("scope") == "local_deepseek_provider_benchmark_recipe_no_model_call"
            and benchmark_recipe.get("local_recipe_ready") is True
            and benchmark_recipe.get("allowed_next_step") == "explicit_deepseek_provider_benchmark_task_with_user_approval"
            and int(benchmark_recipe.get("required_sample_count") or 0) >= 40
            and float(benchmark_recipe.get("required_json_success_rate") or 0) >= 0.9
            and int(benchmark_recipe.get("max_retry_per_sample") or 0) <= 2
            and set(_list(benchmark_recipe.get("phase_keys"))) == REQUIRED_BENCHMARK_RECIPE_PHASES
            and set(benchmark_recipe_rows) == REQUIRED_BENCHMARK_RECIPE_PHASES
            and set(_list(benchmark_recipe.get("allowed_output_fields"))) == REQUIRED_ALLOWED_KEYS
            and {"model_used", "status", "token_usage", "parse_status", "cache_hit_or_miss", "input_hash", "output_hash"}.issubset(
                set(_list(benchmark_recipe.get("required_model_ledger_fields")))
            )
            and "provider benchmark report with at least 40 samples" in _list(benchmark_recipe.get("missing_evidence"))
            and "local retry/repair dry-run as provider benchmark" in _list(benchmark_recipe.get("not_allowed_next_steps"))
            and "benchmark recipe as production completion" in _list(benchmark_recipe.get("not_allowed_next_steps"))
            and benchmark_recipe.get("provider_benchmark_done") is False
            and benchmark_recipe.get("larger_benchmark_done") is False
            and benchmark_recipe.get("provider_response_format_enforced") is False
            and benchmark_recipe.get("bounded_retry_repair_ready") is False
            and benchmark_recipe.get("token_budget_cost_evidence_complete") is False
            and benchmark_recipe.get("auto_after_task_production_ready") is False
            and benchmark_recipe.get("production_deepseek_explanation_complete") is False
            and benchmark_recipe.get("provider_model_called_by_recipe") is False
            and all(row.get("recipe_step_ready") is True for row in benchmark_recipe_rows.values())
            and all(row.get("model_call_status") == "not_called" for row in benchmark_recipe_rows.values())
            and all(row.get("contains_secret") is False for row in benchmark_recipe_rows.values())
            and _flag_false(benchmark_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called", "contains_secret")
            and benchmark_recipe.get("does_not_execute_trades") is True
            and benchmark_recipe.get("does_not_modify_strategy_action") is True
            and benchmark_recipe.get("does_not_override_numeric_values") is True
            and benchmark_recipe.get("does_not_output_strategy_action") is True,
            "Provider benchmark execution recipe must fix the next real benchmark scope while staying local, model-silent, secret-safe, and production-pending.",
        ),
        _row(
            "provider_benchmark_scope_ticket_is_button_gated_preflight",
            benchmark_scope_ticket.get("schema_version") == "factor_deepseek_provider_benchmark_scope_ticket_receipt.v1"
            and benchmark_scope_ticket.get("scope") == "local_deepseek_provider_benchmark_scope_ticket_no_model_call"
            and benchmark_scope_ticket.get("status")
            in {
                "deepseek_provider_benchmark_scope_ticket_missing",
                "deepseek_provider_benchmark_scope_ticket_blocked_preflight",
                "deepseek_provider_benchmark_scope_ticket_ready_secret_pending",
                "deepseek_provider_benchmark_scope_ticket_ready_model_execution_pending",
            }
            and scope_ticket_task.get("route") == "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket"
            and scope_ticket_task.get("button_gated") is True
            and scope_ticket_task.get("current_backend") == "local_deepseek_provider_benchmark_scope_ticket_pipeline"
            and scope_ticket_task.get("external_call_policy") == "local_scope_ticket_no_model_call"
            and scope_ticket_task.get("model_execution_implemented") is False
            and scope_ticket_task.get("provider_benchmark_done") is False
            and scope_ticket_task.get("provider_response_format_enforced") is False
            and scope_ticket_task.get("bounded_retry_repair_executed") is False
            and scope_ticket_task.get("production_deepseek_explanation_complete") is False
            and benchmark_scope_ticket.get("model_execution_implemented") is False
            and benchmark_scope_ticket.get("provider_benchmark_done") is False
            and benchmark_scope_ticket.get("provider_response_format_enforced") is False
            and benchmark_scope_ticket.get("bounded_retry_repair_executed") is False
            and benchmark_scope_ticket.get("token_budget_cost_evidence_complete") is False
            and benchmark_scope_ticket.get("auto_after_task_production_ready") is False
            and benchmark_scope_ticket.get("production_deepseek_explanation_complete") is False
            and benchmark_scope_ticket.get("server_secret_values_read") is False
            and benchmark_scope_ticket.get("env_key_names_exposed") is False
            and benchmark_scope_ticket.get("credential_values_exposed") is False
            and benchmark_scope_ticket.get("model_call_status") == "not_called"
            and benchmark_scope_ticket.get("provider_model_called") is False
            and benchmark_scope_ticket.get("cache_get_external_calls") is False
            and _flag_false(benchmark_scope_ticket, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called", "contains_secret")
            and benchmark_scope_ticket.get("does_not_execute_trades") is True
            and benchmark_scope_ticket.get("does_not_modify_strategy_action") is True
            and benchmark_scope_ticket.get("does_not_override_numeric_values") is True
            and benchmark_scope_ticket.get("does_not_output_strategy_action") is True
            and {"explicit_user_approval", "sample_count_meets_threshold", "provider_response_format_scope", "bounded_retry_budget_scope", "model_ledger_fields_scope", "benchmark_phase_scope", "server_secret_presence_boolean", "scope_ticket_hash_visible", "no_model_call_boundary", "no_trade_action_numeric_boundary", "production_completion_stays_blocked"}.issubset(set(benchmark_scope_ticket_rows))
            and "scope ticket as provider benchmark evidence" in _list(benchmark_scope_ticket.get("not_allowed_next_steps"))
            and "call DeepSeek from scope ticket" in _list(benchmark_scope_ticket.get("not_allowed_next_steps"))
            and "auto_after_task promotion from scope ticket" in _list(benchmark_scope_ticket.get("not_allowed_next_steps"))
            and _list(benchmark_scope_ticket.get("call_ledger"))
            and _dict(_list(benchmark_scope_ticket.get("call_ledger"))[0]).get("api") == "local_deepseek_provider_benchmark_scope_ticket",
            "DeepSeek provider benchmark scope ticket must be a button-gated local POST preflight that can bind a future benchmark scope without model calls, credentials, trades, action/numeric overwrite, or production completion.",
        ),
        _row(
            "deepseek_durable_evidence_recipe_is_local_pending",
            durable_recipe.get("schema_version") == "factor_deepseek_durable_evidence_recipe.v1"
            and durable_recipe.get("status") == "deepseek_durable_evidence_recipe_ready_production_pending"
            and durable_recipe.get("scope") == "local_deepseek_durable_evidence_recipe_no_model_call"
            and durable_recipe.get("local_recipe_ready") is True
            and durable_recipe.get("durable_evidence_complete") is False
            and durable_recipe.get("durable_promotion_ready") is False
            and durable_recipe.get("provider_benchmark_done") is False
            and durable_recipe.get("larger_benchmark_done") is False
            and durable_recipe.get("provider_response_format_enforced") is False
            and durable_recipe.get("response_format_enforced") is False
            and durable_recipe.get("bounded_retry_repair_ready") is False
            and durable_recipe.get("bounded_retry_repair_executed") is False
            and durable_recipe.get("token_budget_cost_evidence_complete") is False
            and durable_recipe.get("auto_after_task_production_ready") is False
            and durable_recipe.get("production_deepseek_explanation_complete") is False
            and durable_recipe.get("provider_model_called_by_recipe") is False
            and durable_recipe.get("cache_get_external_calls") is False
            and _flag_false(durable_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called", "contains_secret")
            and durable_recipe.get("does_not_execute_trades") is True
            and durable_recipe.get("does_not_modify_strategy_action") is True
            and durable_recipe.get("does_not_override_numeric_values") is True
            and durable_recipe.get("does_not_output_strategy_action") is True
            and tuple(_list(durable_recipe.get("evidence_keys"))) == REQUIRED_DURABLE_EVIDENCE_KEYS
            and int(durable_recipe.get("evidence_key_count") or 0) == len(REQUIRED_DURABLE_EVIDENCE_KEYS)
            and int(durable_recipe.get("row_count") or 0) == len(REQUIRED_DURABLE_EVIDENCE_KEYS)
            and durable_evidence_keys == set(REQUIRED_DURABLE_EVIDENCE_KEYS)
            and set(_list(durable_recipe.get("missing_durable_evidence"))) == set(REQUIRED_DURABLE_EVIDENCE_MISSING_KEYS)
            and int(durable_recipe.get("production_blocker_count") or 0) == len(REQUIRED_DURABLE_EVIDENCE_MISSING_KEYS)
            and int(durable_recipe.get("durable_evidence_blocker_count") or 0) == len(REQUIRED_DURABLE_EVIDENCE_MISSING_KEYS)
            and {
                "provider benchmark report with at least 40 samples",
                "provider response_format/json_schema execution evidence",
                "bounded retry/repair execution ledger",
                "redacted model ledger with token usage and hashes",
                "token budget and cost evidence",
                "production promotion review",
            }.issubset(set(_list(durable_recipe.get("required_evidence"))))
            and {
                "treat_durable_recipe_as_provider_benchmark",
                "call DeepSeek from GET cache",
                "call DeepSeek from React render",
                "raw token/key in prompt, ledger, packet, cache, or log",
                "durable recipe as production completion",
                "DeepSeek numeric/action overwrite",
            }.issubset(set(_list(durable_recipe.get("not_allowed_next_steps"))))
            and all(row.get("required_before_production") is True for row in durable_recipe_rows)
            and all(row.get("production_ready") is False for row in durable_recipe_rows)
            and all(row.get("model_call_status") == "not_called" for row in durable_recipe_rows)
            and all(row.get("provider_model_called") is False for row in durable_recipe_rows)
            and all(row.get("external_calls_triggered") is False for row in durable_recipe_rows)
            and all(row.get("tushare_called") is False for row in durable_recipe_rows)
            and all(row.get("deepseek_called") is False for row in durable_recipe_rows)
            and all(row.get("github_called") is False for row in durable_recipe_rows)
            and all(row.get("contains_secret") is False for row in durable_recipe_rows)
            and all(row.get("does_not_execute_trades") is True for row in durable_recipe_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in durable_recipe_rows)
            and all(row.get("does_not_override_numeric_values") is True for row in durable_recipe_rows)
            and all(row.get("does_not_output_strategy_action") is True for row in durable_recipe_rows)
            and _list(durable_recipe.get("call_ledger"))
            and _dict(_list(durable_recipe.get("call_ledger"))[0]).get("api") == "local_deepseek_durable_evidence_recipe",
            "DeepSeek durable evidence recipe must expose provider benchmark, response-format, retry/repair, ledger, cost, redaction, and promotion gaps while staying local, model-silent, secret-safe, no-trade, and production-pending.",
        ),
        _row(
            "deepseek_production_stage_scope_manifest_is_complete_and_pending",
            {row.get("stage_key") for row in deepseek_production_stage_scope_rows}
            == REQUIRED_DEEPSEEK_PRODUCTION_STAGES
            and len(deepseek_production_stage_scope_rows) == len(REQUIRED_DEEPSEEK_PRODUCTION_STAGES)
            and all(row.get("scope") == "deepseek_production_stage_scope_manifest" for row in deepseek_production_stage_scope_rows)
            and all(row.get("required_before_production") is True for row in deepseek_production_stage_scope_rows)
            and all(row.get("current_status") == "local_governance_or_dry_run_only" for row in deepseek_production_stage_scope_rows)
            and all(
                row.get("target_status") == "provider_benchmark_or_runtime_evidence_required"
                for row in deepseek_production_stage_scope_rows
            )
            and all(row.get("provider_benchmark_done") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("response_format_enforced") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("bounded_retry_repair_executed") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("token_budget_cost_evidence_complete") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("auto_after_task_production_ready") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("model_execution_implemented") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("production_deepseek_explanation_complete") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("deepseek_called_by_contract") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("external_calls_triggered") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("tushare_called") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("github_called") is False for row in deepseek_production_stage_scope_rows)
            and all(row.get("does_not_execute_trades") is True for row in deepseek_production_stage_scope_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in deepseek_production_stage_scope_rows)
            and all(row.get("does_not_override_numeric_values") is True for row in deepseek_production_stage_scope_rows)
            and all(row.get("does_not_output_strategy_action") is True for row in deepseek_production_stage_scope_rows)
            and all(row.get("contains_secret") is False for row in deepseek_production_stage_scope_rows),
            "DeepSeek production scope rows must enumerate every pending evidence stage and keep provider benchmark, model execution, automatic production readiness, trades, actions, and secrets disabled.",
        ),
        _row(
            "push_gate_runs_deepseek_contract_after_factor_lab",
            "scripts/deepseek_governance_contract.py" in push_gate_script
            and "DeepSeek governance contract" in push_gate_script
            and "deepseek_governance_contract: passed_local_contract_provider_benchmark_pending" in push_gate_script
            and push_gate_script.find('run_step "Factor Test Lab contract"') < push_gate_script.find('run_step "DeepSeek governance contract"')
            and push_gate_script.find('run_step "DeepSeek governance contract"') < push_gate_script.find('run_step "Candidate Radar contract"'),
            "Push gate must run LTG-07 DeepSeek governance after Factor Test Lab and before Candidate Radar.",
        ),
        _row(
            "script_is_local_no_model_or_provider_execution",
            "command_center_3_deepseek_governance_contract.v1" in this_script
            and "local_deepseek_governance_contract_no_model_call" in this_script
            and "deepseek_production_activation_receipt.v1" in this_script
            and "factor_deepseek_retry_repair_dry_run_contract.v1" in this_script
            and "factor_deepseek_provider_benchmark_execution_recipe.v1" in this_script
            and "factor_deepseek_provider_benchmark_scope_ticket_receipt.v1" in this_script
            and "factor_deepseek_durable_evidence_recipe.v1" in this_script
            and "provider_benchmark_done" in this_script
            and "production_deepseek_explanation_complete" in this_script
            and "deepseek_production_stage_scope_manifest" in this_script
            and "response_format_enforced" in this_script
            and "provider_benchmark_scope_ticket_is_button_gated_preflight" in this_script
            and "deepseek_durable_evidence_recipe_is_local_pending" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("deepseek" + "_adapter") not in this_script
            and ("deepseek" + ".chat") not in this_script
            and ("deepseek" + ".com") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients, model adapters, or network libraries.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_deepseek_governance_contract.v1",
        "status": "deepseek_governance_contract_passed" if not blockers else "deepseek_governance_contract_blocked",
        "scope": "local_deepseek_governance_contract_no_model_call",
        "ltg": "LTG-07/LTG-11",
        "contract_ready": not blockers,
        "manual_explanation_ready": True,
        "provider_benchmark_done": False,
        "larger_benchmark_done": False,
        "response_format_enforced": False,
        "retry_repair_policy_ready": False,
        "retry_repair_dry_run_ready": retry_repair_dry_run.get("local_retry_repair_dry_run_ready") is True,
        "auto_after_task_production_ready": False,
        "deepseek_production_activation_receipt_ready": activation_receipt.get("local_activation_receipt_ready") is True,
        "provider_benchmark_execution_recipe_ready": benchmark_recipe.get("local_recipe_ready") is True,
        "provider_benchmark_scope_ticket_ready": benchmark_scope_ticket.get("local_scope_ticket_ready") is True,
        "provider_benchmark_scope_ticket_status": benchmark_scope_ticket.get("status"),
        "deepseek_durable_evidence_recipe_ready": durable_recipe.get("local_recipe_ready") is True,
        "deepseek_durable_evidence_recipe_status": durable_recipe.get("status"),
        "deepseek_durable_evidence_blocker_count": durable_recipe.get("durable_evidence_blocker_count"),
        "production_deepseek_explanation_complete": False,
        "sanitizer_only": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "governance_mode": governance.get("mode"),
            "configured_auto_after_task": governance.get("configured_auto_after_task"),
            "auto_after_task": governance.get("auto_after_task"),
            "model_call_status": validation.get("model_call_status"),
            "json_audit_status": json_audit.get("status"),
            "json_success_rate": json_audit.get("last_known_mini_benchmark_success_rate"),
            "json_required_success_rate": json_audit.get("required_json_success_rate"),
            "json_production_blockers": json_audit.get("production_blockers"),
            "response_format_status": response_review.get("status"),
            "response_format_production_blockers": response_review.get("production_blockers"),
            "retry_repair_dry_run_status": retry_repair_dry_run.get("status"),
            "retry_repair_case_count": retry_repair_dry_run.get("case_count"),
            "retry_repair_paths": retry_repair_dry_run.get("repair_paths"),
            "activation_receipt_status": activation_receipt.get("status"),
            "activation_receipt_allowed_next_step": activation_receipt.get("allowed_next_step"),
            "activation_receipt_blockers": activation_receipt.get("blockers"),
            "benchmark_recipe_status": benchmark_recipe.get("status"),
            "benchmark_recipe_required_sample_count": benchmark_recipe.get("required_sample_count"),
            "benchmark_recipe_phase_count": benchmark_recipe.get("phase_count"),
            "benchmark_recipe_allowed_next_step": benchmark_recipe.get("allowed_next_step"),
            "benchmark_scope_ticket_status": benchmark_scope_ticket.get("status"),
            "benchmark_scope_ticket_hash_short": benchmark_scope_ticket.get("benchmark_scope_hash_short"),
            "benchmark_scope_ticket_ready": benchmark_scope_ticket.get("local_scope_ticket_ready"),
            "benchmark_scope_ticket_secret_present": benchmark_scope_ticket.get("server_secret_present"),
            "durable_evidence_recipe_status": durable_recipe.get("status"),
            "durable_evidence_recipe_ready": durable_recipe.get("local_recipe_ready"),
            "durable_evidence_key_count": len(durable_recipe_rows),
            "durable_evidence_keys": [row.get("evidence_key") for row in durable_recipe_rows],
            "durable_evidence_missing_keys": durable_recipe.get("missing_durable_evidence"),
            "durable_evidence_blocker_count": durable_recipe.get("durable_evidence_blocker_count"),
            "task_backend": task.get("current_backend"),
            "task_button_gated": task.get("button_gated"),
            "deepseek_production_stage_scope_count": len(deepseek_production_stage_scope_rows),
            "deepseek_production_stage_scope_keys": sorted(
                row.get("stage_key") for row in deepseek_production_stage_scope_rows
            ),
            "deepseek_production_stage_scope_pending_count": sum(
                1
                for row in deepseek_production_stage_scope_rows
                if row.get("production_deepseek_explanation_complete") is False
            ),
        },
        "deepseek_durable_evidence_rows": durable_recipe_rows,
        "deepseek_production_stage_scope_rows": deepseek_production_stage_scope_rows,
        "rows": rows,
        "note": "This is a local push-gate contract. Real provider-backed DeepSeek benchmark, provider response_format enforcement, bounded retry/repair, and production automatic explanation remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-07 DeepSeek governance contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"deepseek_governance_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_benchmark_done: false; response_format_enforced: false; "
            "production_deepseek_explanation_complete: false".format(**contract)
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
