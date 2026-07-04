from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from config import DEEPSEEK_MODEL_CONFIG_KEYS, DEEPSEEK_MODEL_DEFAULTS, get_config_value, get_deepseek_model


PACKET_KEY = "command_center_3_deepseek_model_strategy_cache"
SCHEMA_VERSION = "deepseek_model_strategy_cache.v1"
MODEL_PURPOSES = ("default", "explain", "projection", "factor_explain", "fast", "healthcheck", "feeder")
SAFE_EXPLANATION_FIELDS = (
    "summary",
    "support_notes",
    "suppress_notes",
    "conflict_notes",
    "missing_data_notes",
    "discipline_notes",
)
FORBIDDEN_OUTPUT_TARGETS = (
    "price",
    "holding",
    "factor",
    "operation_zones",
    "strategy_action",
    "trade_order",
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


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "deepseek_model_strategy_cache_not_json_serializable"}


def _active_config_key(purpose: str) -> str | None:
    for key in DEEPSEEK_MODEL_CONFIG_KEYS.get(purpose, ()):
        if get_config_value(key):
            return key
    return None


def build_deepseek_model_strategy_ref(purpose: str = "default") -> dict[str, Any]:
    selected = str(purpose or "default").strip().lower()
    if selected not in DEEPSEEK_MODEL_CONFIG_KEYS:
        selected = "default"
    active_key = _active_config_key(selected)
    config_keys = list(DEEPSEEK_MODEL_CONFIG_KEYS.get(selected, ()))
    fallback_model = DEEPSEEK_MODEL_DEFAULTS.get(selected, DEEPSEEK_MODEL_DEFAULTS["default"])
    return {
        "purpose": selected,
        "model": get_deepseek_model(selected),
        "fallback_model": fallback_model,
        "config_keys": config_keys,
        "active_config_key": active_key,
        "uses_configured_value": bool(active_key),
        "uses_safe_default": not bool(active_key),
        "model_source": f"config.get_deepseek_model('{selected}')",
        "does_not_hardcode_model": True,
        "contains_secret": False,
        "call_policy": "manual_only",
        "external_call_on_cache_read": False,
    }


def _purpose_row(purpose: str) -> dict[str, Any]:
    return build_deepseek_model_strategy_ref(purpose)


def _latest_factor_quant_hub_packet() -> dict[str, Any]:
    try:
        from server.services import factor_service
        from storage.sqlite_meta import SQLiteMetaStore

        if not factor_service.SQLITE_META_PATH.exists():
            return {}
        packet = SQLiteMetaStore(factor_service.SQLITE_META_PATH).read_packet(
            "command_center_factor_quant_hub_packet"
        )
    except Exception:
        return {}
    return dict(packet) if isinstance(packet, dict) else {}


def _latest_provider_benchmark_scope_ticket_receipt() -> dict[str, Any]:
    packet = _latest_factor_quant_hub_packet()
    receipt = packet.get("deepseek_provider_benchmark_scope_ticket_receipt")
    return dict(receipt) if isinstance(receipt, dict) else {}


def _latest_provider_benchmark_execution_request_receipt() -> dict[str, Any]:
    packet = _latest_factor_quant_hub_packet()
    receipt = packet.get("deepseek_provider_benchmark_execution_request_receipt")
    return dict(receipt) if isinstance(receipt, dict) else {}


def _deepseek_production_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key, stage_label in sorted(DEEPSEEK_PRODUCTION_STAGE_LABELS.items()):
        rows.append({
            "stage_key": stage_key,
            "stage_label": stage_label,
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
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "deepseek_called_by_contract": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_override_numeric_values": True,
            "does_not_output_strategy_action": True,
            "contains_secret": False,
            "is_production_evidence": False,
        })
    return rows


def read_deepseek_model_strategy_cache() -> dict[str, Any]:
    rows = [_purpose_row(purpose) for purpose in MODEL_PURPOSES]
    configured_count = sum(1 for row in rows if row["uses_configured_value"])
    fast_purposes = [row["purpose"] for row in rows if row["purpose"] in {"fast", "healthcheck", "feeder"}]
    explain_purposes = [row["purpose"] for row in rows if row["purpose"] in {"default", "explain", "projection", "factor_explain"}]
    loaded_at = _now_iso()
    scope_ticket_receipt = _latest_provider_benchmark_scope_ticket_receipt()
    scope_ticket_ready = scope_ticket_receipt.get("local_scope_ticket_ready") is True
    scope_ticket_status = str(
        scope_ticket_receipt.get("status") or "deepseek_provider_benchmark_scope_ticket_missing"
    )
    scope_ticket_hash = str(scope_ticket_receipt.get("benchmark_scope_hash") or "")
    scope_ticket_hash_short = str(scope_ticket_receipt.get("benchmark_scope_hash_short") or "")
    execution_request_receipt = _latest_provider_benchmark_execution_request_receipt()
    execution_request_ready = execution_request_receipt.get("local_execution_request_ready") is True
    execution_request_status = str(
        execution_request_receipt.get("status") or "deepseek_provider_benchmark_execution_request_missing"
    )
    provider_benchmark_done = (
        scope_ticket_receipt.get("provider_benchmark_done") is True
        or execution_request_receipt.get("provider_benchmark_done") is True
    )
    model_execution_task_implemented = False
    model_ledger_ready = False
    sanitizer_ready = False
    redaction_review_ready = False
    cost_accounting_ready = False
    output_acceptance_ready = False
    response_format_enforced = False
    bounded_retry_repair_ready = False
    real_call_gate_specs = [
        (
            "scope_ticket_ready",
            scope_ticket_ready,
            "本地 scope ticket 已绑定 DeepSeek provider benchmark 范围",
            "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket",
        ),
        (
            "execution_request_ready",
            execution_request_ready,
            "本地 execution-request ticket 已绑定 latest scope hash",
            "POST /api/factor-quant/deepseek-provider-benchmark-execution-request",
        ),
        (
            "model_execution_task_implemented",
            model_execution_task_implemented,
            "真实 DeepSeek governed executor 已实现并只允许按钮门控",
            "future POST model execution task",
        ),
        (
            "provider_benchmark_done",
            provider_benchmark_done,
            "真实 provider-backed JSON stability benchmark 已完成",
            "future governed executor evidence",
        ),
        ("model_ledger_ready", model_ledger_ready, "model_ledger 可审计回放", "future model ledger"),
        ("sanitizer_ready", sanitizer_ready, "输出 sanitizer 已生产化", "sanitizer contract"),
        ("redaction_review_ready", redaction_review_ready, "白名单字段和脱敏审查已通过", "redaction review"),
        ("cost_accounting_ready", cost_accounting_ready, "token/cost 账本已可回放", "cost ledger"),
        ("output_acceptance_ready", output_acceptance_ready, "安全输出验收已通过", "output acceptance"),
        (
            "response_format_enforced",
            response_format_enforced,
            "provider response_format / JSON schema 强约束已执行",
            "provider response_format evidence",
        ),
        (
            "bounded_retry_repair_ready",
            bounded_retry_repair_ready,
            "有限重试和修复策略已验收",
            "bounded retry repair evidence",
        ),
    ]
    real_call_gate_rows = [
        {
            "gate_key": key,
            "passed": passed,
            "status": "ready" if passed else "blocked",
            "evidence": evidence,
            "next_evidence": next_evidence,
            "blocks_real_execution": not passed,
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "contains_secret": False,
        }
        for key, passed, evidence, next_evidence in real_call_gate_specs
    ]
    real_call_blockers = [
        row["gate_key"]
        for row in real_call_gate_rows
        if row["blocks_real_execution"] is True
    ]
    real_call_allowed_now = not real_call_blockers
    production_stage_scope_rows = _deepseek_production_stage_scope_rows()
    production_stage_pending_count = sum(
        1
        for row in production_stage_scope_rows
        if row["production_deepseek_explanation_complete"] is False
    )
    production_stage_scope_manifest = {
        "schema_version": "deepseek_production_stage_scope_manifest.v1",
        "status": "deepseek_production_stage_scope_visible_model_execution_pending",
        "scope": "local_model_strategy_cache_deepseek_stage_scope_no_model_call",
        "stage_count": len(production_stage_scope_rows),
        "pending_stage_count": production_stage_pending_count,
        "production_deepseek_explanation_complete": False,
        "real_call_allowed_now": real_call_allowed_now,
        "provider_benchmark_done": False,
        "response_format_enforced": False,
        "bounded_retry_repair_executed": False,
        "token_budget_cost_evidence_complete": False,
        "auto_after_task_production_ready": False,
        "model_execution_implemented": False,
        "cache_only_readback": True,
        "creates_task": False,
        "calls_model": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
        "contains_secret": False,
        "is_production_evidence": False,
    }
    strict_closeout_gate_rows = [
        {
            "gate_key": "provider_benchmark_and_model_ledger_missing",
            "current_status": "real DeepSeek call blocked until governed executor evidence complete",
            "strict_closeout_state": "strict closeout remains blocked",
            "can_close_ltg07_now": False,
            "evidence_required": "provider benchmark / model ledger / response_format / retry-repair / cost-redaction / promotion",
            "deepseek_production_stage_scope_count": len(production_stage_scope_rows),
            "pending_stage_count": production_stage_pending_count,
            "real_call_allowed_now": real_call_allowed_now,
            "production_deepseek_explanation_complete": False,
            "provider_benchmark_done": False,
            "model_ledger_evidence_done": False,
            "response_format_enforced": False,
            "bounded_retry_repair_executed": False,
            "token_budget_cost_evidence_complete": False,
            "auto_after_task_production_ready": False,
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_override_numeric_values": True,
            "does_not_output_strategy_action": True,
            "contains_secret": False,
            "is_production_evidence": False,
        },
        {
            "gate_key": "safe_output_only_nonblocking_paths",
            "current_status": "DeepSeek may explain allowed fields only and does not block Tushare-first, Factor light, or Next Session",
            "strict_closeout_state": "strict closeout remains blocked",
            "can_close_ltg07_now": False,
            "allowed_output_fields": list(SAFE_EXPLANATION_FIELDS),
            "forbidden_output_targets": list(FORBIDDEN_OUTPUT_TARGETS),
            "deepseek_is_data_source": False,
            "deepseek_blocks_tushare_factor_next": False,
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_override_numeric_values": True,
            "does_not_output_strategy_action": True,
            "contains_secret": False,
            "is_production_evidence": False,
        },
        {
            "gate_key": "LTG-12 交易隔离支撑",
            "current_status": "research-only explanation boundary; no broker connection, no order endpoint, no strategy action mutation",
            "strict_closeout_state": "trade isolation remains enforced",
            "can_close_ltg07_now": False,
            "real_trading_connected": False,
            "broker_adapter_connected": False,
            "order_endpoint_present": False,
            "strategy_action_mutated": False,
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_override_numeric_values": True,
            "does_not_output_strategy_action": True,
            "contains_secret": False,
            "is_production_evidence": False,
        },
    ]
    governed_executor = {
        "schema_version": "deepseek_governed_executor_status.v1",
        "status": "governed_executor_execution_request_ready_model_ledger_pending"
        if execution_request_ready
        else "governed_executor_scope_ticket_ready_execution_request_pending"
        if scope_ticket_ready
        else "governed_executor_pending_model_ledger",
        "execution_route": "POST /api/factor-quant/deepseek-explain",
        "execution_route_semantics": "guarded_prompt_or_sanitizer_no_model_call",
        "prompt_sanitizer_route": "POST /api/factor-quant/deepseek-explain",
        "future_model_execution_route": "future POST governed DeepSeek executor",
        "real_model_execution_route_implemented": False,
        "scope_ticket_route": "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket",
        "execution_request_route": "POST /api/factor-quant/deepseek-provider-benchmark-execution-request",
        "model_call_default": "off",
        "scope_ticket_ready": scope_ticket_ready,
        "provider_benchmark_scope_ticket_ready": scope_ticket_ready,
        "provider_benchmark_scope_ticket_status": scope_ticket_status,
        "provider_benchmark_scope_ticket_source_packet_present": bool(scope_ticket_receipt),
        "provider_benchmark_scope_hash": scope_ticket_hash,
        "provider_benchmark_scope_hash_short": scope_ticket_hash_short,
        "provider_benchmark_scope_hash_safe_to_bind": bool(scope_ticket_ready and scope_ticket_hash and len(scope_ticket_hash) == 64),
        "provider_benchmark_scope_ticket_model_call_status": str(
            scope_ticket_receipt.get("model_call_status") or "not_called"
        ),
        "provider_benchmark_scope_ticket_cache_read_initializes_ticket": False,
        "provider_benchmark_execution_request_ready": execution_request_ready,
        "provider_benchmark_execution_request_status": execution_request_status,
        "provider_benchmark_execution_request_source_packet_present": bool(execution_request_receipt),
        "provider_benchmark_execution_request_model_task_created": False,
        "provider_benchmark_execution_request_cache_read_initializes_ticket": False,
        "provider_benchmark_execution_request_is_not_model_execution": True,
        "provider_benchmark_execution_request_allowed_next_step": str(
            execution_request_receipt.get("allowed_next_step") or "run_deepseek_provider_benchmark_scope_ticket"
        ),
        "provider_benchmark_execution_request_scope_hash_matches_latest": execution_request_receipt.get("requested_scope_hash_matches_latest") is True,
        "model_execution_task_implemented": model_execution_task_implemented,
        "provider_benchmark_done": provider_benchmark_done,
        "model_ledger_ready": model_ledger_ready,
        "model_ledger_evidence_done": model_ledger_ready,
        "sanitizer_ready": sanitizer_ready,
        "redaction_review_ready": redaction_review_ready,
        "cost_accounting_ready": cost_accounting_ready,
        "output_acceptance_ready": output_acceptance_ready,
        "response_format_enforced": response_format_enforced,
        "bounded_retry_repair_ready": bounded_retry_repair_ready,
        "real_call_allowed_now": real_call_allowed_now,
        "real_call_blockers": real_call_blockers,
        "real_call_blocker_count": len(real_call_blockers),
        "real_call_gate_rows": real_call_gate_rows,
        "real_call_gate_row_count": len(real_call_gate_rows),
        "real_call_gate_rows_are_cache_only": True,
        "real_call_gate_rows_create_task": False,
        "real_call_gate_rows_call_model": False,
        "real_call_gate_rows_contain_secret": False,
        "real_call_gate_summary": "real_deepseek_call_blocked_until_governed_executor_evidence_complete"
        if not real_call_allowed_now
        else "real_deepseek_call_allowed_by_governed_executor",
        "production_stage_scope_manifest": production_stage_scope_manifest,
        "production_stage_scope_rows": production_stage_scope_rows,
        "production_stage_scope_row_count": len(production_stage_scope_rows),
        "production_stage_pending_count": production_stage_pending_count,
        "strict_closeout_gate_rows": strict_closeout_gate_rows,
        "strict_closeout_gate_row_count": len(strict_closeout_gate_rows),
        "strict_closeout_state": "strict closeout remains blocked",
        "can_close_ltg07_now": False,
        "real_call_requires": [
            "explicit_post_task",
            "model_execution_task_implemented",
            "provider_benchmark_done",
            "model_ledger",
            "sanitizer",
            "redaction_review",
            "cost_accounting",
            "output_acceptance",
            "response_format_enforced",
            "bounded_retry_repair",
        ],
        "does_not_block_tushare_first_or_basic_maps": True,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "deepseek_called": False,
        "contains_secret": False,
        "does_not_override_prices": True,
        "does_not_override_holdings": True,
        "does_not_override_factors": True,
        "does_not_override_operation_zones": True,
        "does_not_modify_strategy_action": True,
        "ordinary_status_label": "P5 execution-request ticket 已本地回读；真实 DeepSeek 调用仍等 governed benchmark / model_ledger / sanitizer / output acceptance。"
        if execution_request_ready
        else "P5 scope ticket 已本地回读；下一步是本地 execution-request ticket，真实 DeepSeek 调用仍等 model_ledger / sanitizer / output acceptance。"
        if scope_ticket_ready
        else "DeepSeek 等 governed executor；Tushare-first 和基础图谱可先走。",
        "ordinary_next_allowed_action": "保留 Tushare-first / Factor light / Next Session 先走；下一步只能手工提交未来 governed provider benchmark，并绑定本地 execution-request scope。"
        if execution_request_ready
        else "保留 Tushare-first / Factor light / Next Session 先走；下一步只可做本地 execution-request ticket，并继续等待 model_ledger，不从 GET cache 调模型。"
        if scope_ticket_ready
        else "先继续 Tushare-first、Factor light 和 Next Session 本地回放；DeepSeek 真实解释等 governed executor 单独验收。",
        "ordinary_required_before_real_call": "需要 model_ledger / sanitizer / redaction review / cost accounting / output acceptance 全部就绪。",
        "ordinary_nonblocking_boundary": "DeepSeek 状态只解释已有证据，不作为数据源、不替代价格/持仓/因子/operation_zones，也不生成买卖动作。",
        "ordinary_safe_to_ignore_for_basic_maps": True,
        "ordinary_blocking_state": "execution_request_ready_model_ledger_pending_not_blocking_tushare_or_basic_maps"
        if execution_request_ready
        else "scope_ticket_ready_execution_request_pending_not_blocking_tushare_or_basic_maps"
        if scope_ticket_ready
        else "pending_model_ledger_not_blocking_tushare_or_basic_maps",
        "ordinary_allowed_output_fields": list(SAFE_EXPLANATION_FIELDS),
        "ordinary_forbidden_output_targets": list(FORBIDDEN_OUTPUT_TARGETS),
        "ordinary_output_contract_label": "仅允许安全解释字段；禁止覆盖价格、持仓、factor、operation_zones、strategy action 或交易动作。",
        "ordinary_output_contract_is_cache_only": True,
        "ordinary_output_contract_creates_task": False,
        "ordinary_output_contract_calls_model": False,
        "ordinary_output_contract_is_production_evidence": False,
    }
    ordinary_one_screen_summary = {
        "schema_version": "deepseek_governed_executor_one_screen_summary.v1",
        "status": "real_call_allowed_governed_executor_ready"
        if real_call_allowed_now
        else "real_call_blocked_basic_research_nonblocking",
        "headline": "DeepSeek 已满足受控调用闸门"
        if real_call_allowed_now
        else "DeepSeek 暂不调用，Tushare-first 和基础图谱可继续",
        "current_state": governed_executor["ordinary_status_label"],
        "next_action": governed_executor["ordinary_next_allowed_action"],
        "required_before_real_call": governed_executor["ordinary_required_before_real_call"],
        "basic_research_boundary": "P1 Tushare-first、P2 小数据写入和 P3 基础图谱不等待 DeepSeek；P5 单独补 governed executor。",
        "safe_output_fields": list(SAFE_EXPLANATION_FIELDS),
        "forbidden_output_targets": list(FORBIDDEN_OUTPUT_TARGETS),
        "real_call_allowed_now": real_call_allowed_now,
        "real_call_blocker_count": len(real_call_blockers),
        "cache_only_readback": True,
        "creates_task": False,
        "calls_model": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "is_production_evidence": False,
    }
    ordinary_checkpoint_rows = [
        {
            "checkpoint": "1. 当前能否继续投研",
            "current_state": "P1 Tushare-first / P2 小数据 / P3 基础图谱不等待 DeepSeek",
            "user_next_step": "先继续下一票雷达确认、股票量化推演和次日图谱本地回放",
            "evidence": "ordinary_one_screen_summary.basic_research_boundary",
            "boundary": "DeepSeek pending 不阻塞基础投研；本行只读 cache，不创建 task。",
        },
        {
            "checkpoint": "2. 真实模型调用",
            "current_state": "已放行" if real_call_allowed_now else f"未放行：{len(real_call_blockers)} 项 blocker",
            "user_next_step": governed_executor["ordinary_next_allowed_action"],
            "evidence": "governed_executor.real_call_gate_rows",
            "boundary": "真实调用必须等 POST task、model_ledger、sanitizer、redaction、cost 和 output acceptance；GET cache 不调用模型。",
        },
        {
            "checkpoint": "3. 安全输出范围",
            "current_state": "仅允许 summary / support_notes / suppress_notes / conflict_notes / missing_data_notes / discipline_notes",
            "user_next_step": "只把模型当已有证据解释层，不当数据源或动作源。",
            "evidence": "ordinary_allowed_output_fields + ordinary_forbidden_output_targets",
            "boundary": "禁止覆盖 price、holding、factor、operation_zones、strategy_action 或 trade_order。",
        },
        {
            "checkpoint": "4. 当前补证动作",
            "current_state": governed_executor["ordinary_blocking_state"],
            "user_next_step": "需要时只生成本地 scope ticket / execution-request；真实 DeepSeek 继续等待 governed executor。",
            "evidence": "provider_benchmark_scope_ticket_status + provider_benchmark_execution_request_status",
            "boundary": "本地票据是 scope/execution-request，不是 model_ledger、模型输出或 production evidence。",
        },
    ]
    for row in ordinary_checkpoint_rows:
        row.update({
            "schema_version": "deepseek_governed_executor_checkpoint_rows.v1",
            "cache_only_readback": True,
            "creates_task": False,
            "calls_model": False,
            "contains_secret": False,
            "external_calls_triggered": False,
            "deepseek_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "is_production_evidence": False,
        })
    governed_executor["ordinary_one_screen_summary"] = ordinary_one_screen_summary
    governed_executor["ordinary_checkpoint_rows"] = ordinary_checkpoint_rows

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": loaded_at,
        "summary": "DeepSeek 模型策略只读展示；模型名来自 DEEPSEEK_*_MODEL 配置或集中默认值，不在调用点硬编码。",
        "governed_executor": governed_executor,
        "ordinary_one_screen_summary": ordinary_one_screen_summary,
        "ordinary_checkpoint_rows": ordinary_checkpoint_rows,
        "deepseek_production_stage_scope_manifest": production_stage_scope_manifest,
        "deepseek_production_stage_scope_rows": production_stage_scope_rows,
        "deepseek_strict_closeout_gate_rows": strict_closeout_gate_rows,
        "model_rows": rows,
        "purpose_groups": {
            "explain_grade": explain_purposes,
            "fast_grade": fast_purposes,
        },
        "counts": {
            "purpose_count": len(rows),
            "configured_count": configured_count,
            "safe_default_count": len(rows) - configured_count,
            "ordinary_checkpoint_row_count": len(ordinary_checkpoint_rows),
            "deepseek_production_stage_scope_row_count": len(production_stage_scope_rows),
            "deepseek_production_stage_pending_count": production_stage_pending_count,
            "deepseek_strict_closeout_gate_row_count": len(strict_closeout_gate_rows),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_deepseek": True,
            "does_not_read_api_keys": True,
            "does_not_expose_credentials": True,
            "does_not_call_tushare": True,
            "does_not_call_github": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_model_call": True,
            "governed_executor_required_for_real_deepseek": True,
            "deepseek_does_not_block_tushare_or_basic_maps": True,
            "model_names_are_configurable": True,
            "callsite_hardcoding_allowed": False,
            "contains_secret": False,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_deepseek_model_strategy_cache",
                "source": "config.get_deepseek_model and optional persisted factor quant DeepSeek scope ticket receipt",
                "row_count": len(rows),
                "local_fetched_at": loaded_at,
                "call_status": "cache_read",
                "external": False,
            }
        ],
        "warnings": [
            "GET /api/model-strategy/cache 只读展示 DeepSeek 模型策略，不调用模型。",
            "模型名可通过 DEEPSEEK_EXPLAIN_MODEL、DEEPSEEK_FAST_MODEL、DEEPSEEK_DEFAULT_MODEL 调整；页面不展示凭据。",
            "DeepSeek 只能解释已有结构化结果，不作为数据源，也不修改 strategy action。",
        ],
    }
    return _json_safe(packet)
