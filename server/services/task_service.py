from __future__ import annotations

import datetime as _dt
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from config import DEEPSEEK_MODEL_CONFIG_KEYS
from storage.sqlite_meta import SQLiteMetaStore

from .model_strategy_service import build_deepseek_model_strategy_ref
from .request_local_memo import memoize_request_local_read


_TASKS: dict[str, dict[str, Any]] = {}
TASK_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
SECRET_KEYWORDS = ("token", "api_key", "secret", "password", "authorization", "bearer", "cookie")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
DEFAULT_SNAPSHOT_CACHE_PATH = PROJECT_ROOT / ".stock_ming_cache" / "command_center_latest.json"
SQLITE_META_PATH = DEFAULT_SQLITE_META_PATH
TUSHARE_OPTIONAL_EXTENDED_APIS = [
    "margin_detail",
    "top_list",
    "top_inst",
    "stk_limit",
    "limit_list_d",
    "limit_cpt_list",
    "cyq_perf",
    "cyq_chips",
    "anns_d",
    "forecast",
    "fina_indicator",
    "stk_holdertrade",
    "share_float",
    "pledge_stat",
    "pledge_detail",
    "stk_surv",
]

TASK_CATALOG = [
    {
        "task_type": "refresh_tushare_facts",
        "route": "POST /api/tasks/refresh-tushare-facts",
        "label": "刷新 Tushare A 股事实",
        "output_packet_key": "command_center_tushare_refresh_packet",
        "button_gated": True,
        "current_backend": "button_gated_tushare_pipeline",
        "external_call_policy": "button_gated_tushare_task",
        "possible_external_sources": ["tushare"],
        "default_core_apis": ["daily", "daily_basic", "moneyflow"],
        "calendar_apis": ["trade_cal"],
        "optional_extended_apis": list(TUSHARE_OPTIONAL_EXTENDED_APIS),
        "parquet_enabled_apis": ["daily", "daily_basic", "moneyflow", "trade_cal"],
        "extended_validation_scope": "button_payload_apis_or_include_extended",
        "api_validation_matrix_policy": "selected APIs use call_ledger; unselected APIs are capability matrix only and must not be treated as verified.",
        "api_acceptance_audit_contract": "call_ledger_required_fields / safe statuses / no false verified / no false parquet claim / no secret leakage.",
        "failure_mode_qa_contract": "classifies existing call_ledger rows into empty/no-record, permission_denied, parse_failed/invalid_result, missing_required_parameter, provider_error, and matrix_only_not_requested; does not call provider.",
        "failure_mode_qa_is_provider_acceptance": False,
        "request_parameter_qa_contract": "declares per-interface safe request params, ts_code preflight blocking, date context params, and matrix-only boundaries; does not call provider.",
        "request_parameter_qa_is_provider_acceptance": False,
        "provider_target_sample_plan_contract": "declares target-domain sample windows, required APIs, request context, success evidence, and failure evidence for future provider-backed acceptance; plan only.",
        "provider_target_sample_plan_is_provider_acceptance": False,
        "provider_target_sample_acceptance_contract": "explicit target-sample acceptance payload plus call_ledger evidence review; reviewable milestone only, not full-interface production acceptance.",
        "provider_target_sample_acceptance_mode": "provider_target_sample_acceptance",
        "provider_target_sample_acceptance_mode_requires_explicit_payload": True,
        "provider_target_sample_acceptance_is_full_interface_acceptance": False,
        "provider_evidence_gap_audit_contract": "local target-domain evidence gap ledger; reads call_ledger/sample-plan/promotion evidence and does not call provider or promote acceptance.",
        "provider_evidence_gap_audit_is_provider_acceptance": False,
        "provider_target_sample_execution_recipe": "local ordered recipe for future explicit target-sample provider execution and promotion review; does not call Tushare or create tasks.",
        "provider_target_sample_execution_recipe_is_provider_acceptance": False,
        "provider_target_sample_execution_recipe_creates_task": False,
        "tushare_durable_evidence_recipe": "local LTG-02 durable evidence checklist for target samples, call ledger, failure modes, full-interface promotion, and storage/cache promotion; does not call Tushare or create tasks.",
        "tushare_durable_evidence_recipe_is_provider_acceptance": False,
        "tushare_durable_evidence_recipe_creates_task": False,
        "provider_acceptance_modes": ["provider_backed_trade_cal_long_window", "provider_target_sample_acceptance"],
        "full_interface_provider_production_acceptance_mode": "full_interface_provider_production",
        "full_interface_provider_production_route": "POST /api/tasks/refresh-tushare-facts",
        "full_interface_provider_production_requires_ready_target_sample_execution_request": True,
        "full_interface_provider_production_requires_bound_scope_hash": True,
        "full_interface_provider_production_requires_explicit_operator_approval": True,
        "full_interface_provider_production_requires_real_provider_adapter": True,
        "full_interface_provider_production_requires_all_interfaces_success_non_empty": True,
        "full_interface_provider_production_requires_safe_failure_mode_taxonomy": True,
        "full_interface_provider_production_requires_parquet_promotion": True,
        "full_interface_provider_production_requires_durable_sqlite_stage_and_final_readback": True,
        "synthetic_adapter_can_promote_production": False,
        "trade_cal_provider_acceptance_mode_requires_explicit_payload": True,
        "trade_cal_provider_acceptance_requires_long_window_days": 730,
        "trade_cal_provider_acceptance_requires_failure_mode_evidence": True,
        "trade_cal_provider_acceptance_requires_freshness_replay": True,
        "trade_cal_provider_acceptance_real_route_requires_execution_request": True,
        "trade_cal_provider_acceptance_requires_bound_execution_request_scope_hash": True,
        "trade_cal_provider_acceptance_requires_execution_request_exchange_window_match": True,
        "trade_cal_provider_acceptance_gate_blocks_before_provider_adapter_load": True,
        "trade_cal_provider_acceptance_is_full_interface_acceptance": False,
        "full_interface_acceptance_done": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_trade_cal_provider_acceptance_dry_run",
        "route": "POST /api/data-health/trade-cal-provider-acceptance-dry-run",
        "label": "生成 trade_cal provider 验收 dry-run ticket",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_trade_cal_acceptance_dry_run_pipeline",
        "external_call_policy": "local_trade_cal_acceptance_dry_run_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-01/LTG-02",
        "local_dry_run_only": True,
        "target_provider_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_acceptance_mode": "provider_backed_trade_cal_long_window",
        "allowed_apis": ["trade_cal"],
        "minimum_acceptance_window_days": 730,
        "requires_user_approval_flag": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "provider_execution_implemented": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_provider_target_sample_execution_recipe_seed",
        "route": "POST /api/tasks/tushare-provider-target-sample-execution-recipe-seed",
        "label": "生成 Tushare target-sample provider 执行 recipe seed",
        "output_packet_key": "command_center_tushare_provider_target_sample_execution_recipe_packet",
        "button_gated": True,
        "current_backend": "local_tushare_provider_target_sample_execution_recipe_seed_pipeline",
        "external_call_policy": "local_tushare_provider_target_sample_execution_recipe_seed_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02",
        "local_recipe_seed_only": True,
        "target_provider_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_provider_task_type": "refresh_tushare_facts",
        "target_acceptance_mode": "provider_target_sample_acceptance",
        "allowed_target_groups": [
            "margin_financing",
            "dragon_tiger",
            "limit_emotion",
            "chip_distribution",
            "financial_disclosure",
            "hard_risk",
        ],
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_target_sample_execution_recipe_creates_task": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_provider_target_sample_execution_request",
        "route": "POST /api/tasks/tushare-provider-target-sample-execution-request",
        "label": "生成 Tushare target-sample provider 执行请求 ticket",
        "output_packet_key": "command_center_tushare_provider_target_sample_execution_request_packet",
        "button_gated": True,
        "current_backend": "local_tushare_provider_target_sample_execution_request_pipeline",
        "external_call_policy": "local_tushare_provider_target_sample_execution_request_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02",
        "local_execution_request_only": True,
        "requires_prior_task_type": "refresh_tushare_facts",
        "requires_bound_execution_recipe_scope_hash": True,
        "target_provider_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_provider_task_type": "refresh_tushare_facts",
        "target_acceptance_mode": "provider_target_sample_acceptance",
        "allowed_target_groups": [
            "trade_calendar",
            "margin_financing",
            "dragon_tiger",
            "limit_emotion",
            "chip_distribution",
            "financial_disclosure",
            "hard_risk",
        ],
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_provider_target_sample_failure_window_review",
        "route": "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        "label": "审查 Tushare target-sample failure-mode/window blocker",
        "output_packet_key": "command_center_tushare_provider_target_sample_failure_window_review_packet",
        "button_gated": True,
        "current_backend": "local_tushare_provider_target_sample_failure_window_review_pipeline",
        "external_call_policy": "local_tushare_provider_target_sample_failure_window_review_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02",
        "local_review_only": True,
        "requires_prior_task_type": "refresh_tushare_facts",
        "requires_prior_acceptance_mode": "provider_target_sample_acceptance",
        "reads_existing_provider_call_ledger": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_review": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_provider_target_sample_storage_promotion_review",
        "route": "POST /api/tasks/tushare-provider-target-sample-storage-promotion-review",
        "label": "审查 Tushare target-sample storage/cache promotion boundary",
        "output_packet_key": "command_center_tushare_target_sample_storage_promotion_review_packet",
        "button_gated": True,
        "current_backend": "local_tushare_target_sample_storage_promotion_review_pipeline",
        "external_call_policy": "local_tushare_target_sample_storage_promotion_review_no_external_or_storage_write",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02/LTG-05",
        "local_storage_promotion_review_only": True,
        "requires_prior_task_type": "run_tushare_provider_target_sample_failure_window_review",
        "reads_existing_provider_call_ledger": True,
        "reads_storage_current_result_cache": True,
        "writes_parquet": False,
        "writes_manifest": False,
        "writes_cache": False,
        "deletes_artifacts": False,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_review": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_provider_target_sample_permission_followup_ticket",
        "route": "POST /api/tasks/tushare-provider-target-sample-permission-followup-ticket",
        "label": "生成 Tushare target-sample permission follow-up ticket",
        "output_packet_key": "command_center_tushare_provider_target_sample_permission_followup_packet",
        "button_gated": True,
        "current_backend": "local_tushare_provider_target_sample_permission_followup_pipeline",
        "external_call_policy": "local_tushare_provider_target_sample_permission_followup_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02",
        "local_permission_followup_ticket_only": True,
        "requires_prior_task_type": "run_tushare_provider_target_sample_failure_window_review",
        "requires_permission_denied_failure_mode": True,
        "target_provider_task_route": "future explicit permission-upgraded provider task or alternative hard-risk evidence task",
        "target_acceptance_mode": "provider_permission_upgrade_or_alternative_hard_risk_evidence",
        "allowed_target_groups": ["hard_risk"],
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_alternative_hard_risk_evidence_scope_ticket",
        "route": "POST /api/tasks/tushare-alternative-hard-risk_evidence-scope-ticket",
        "label": "生成 hard-risk 替代证据 scope ticket",
        "output_packet_key": "command_center_tushare_alternative_hard_risk_evidence_scope_packet",
        "button_gated": True,
        "current_backend": "local_tushare_alternative_hard_risk_evidence_scope_pipeline",
        "external_call_policy": "local_tushare_alternative_hard_risk_evidence_scope_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-02",
        "local_alternative_hard_risk_scope_ticket_only": True,
        "requires_prior_task_type": "run_tushare_provider_target_sample_permission_followup_ticket",
        "requires_bound_permission_followup_scope_hash": True,
        "target_acceptance_mode": "alternative_hard_risk_evidence_scope",
        "allowed_target_groups": ["hard_risk"],
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_trade_cal_provider_acceptance_execution_request",
        "route": "POST /api/data-health/trade-cal-provider-acceptance-execution-request",
        "label": "生成 trade_cal provider 验收执行请求 ticket",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_trade_cal_acceptance_execution_request_pipeline",
        "external_call_policy": "local_trade_cal_acceptance_execution_request_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-01/LTG-02",
        "local_execution_request_only": True,
        "requires_prior_task_type": "run_trade_cal_provider_acceptance_dry_run",
        "requires_bound_scope_hash": True,
        "target_provider_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_provider_task_type": "refresh_tushare_facts",
        "target_acceptance_mode": "provider_backed_trade_cal_long_window",
        "allowed_apis": ["trade_cal"],
        "minimum_acceptance_window_days": 730,
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_trade_cal_provider_acceptance_promotion_review",
        "route": "POST /api/data-health/trade-cal-provider-acceptance-promotion-review",
        "label": "审查 trade_cal provider 验收提升证据",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_trade_cal_acceptance_promotion_review_pipeline",
        "external_call_policy": "local_trade_cal_acceptance_promotion_review_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": [],
        "ltg": "LTG-01/LTG-02/LTG-11",
        "local_promotion_review_only": True,
        "requires_prior_task_type": "run_trade_cal_provider_acceptance_execution_request",
        "requires_prior_provider_evidence": True,
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_review": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "ready_for_production_freshness_release_review": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_trade_cal_provider_acceptance_release_review",
        "route": "POST /api/data-health/trade-cal-provider-acceptance-release-review",
        "label": "审查 trade_cal provider 验收 release evidence",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_trade_cal_acceptance_release_review_pipeline",
        "external_call_policy": "local_trade_cal_acceptance_release_review_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": [],
        "ltg": "LTG-01/LTG-11",
        "local_release_review_only": True,
        "requires_prior_task_type": "run_trade_cal_provider_acceptance_promotion_review",
        "requires_prior_provider_evidence": True,
        "requires_matching_remote_ci_green": True,
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_review": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "ready_for_production_freshness_promotion": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_trade_cal_provider_acceptance_production_promotion_review",
        "route": "POST /api/data-health/trade-cal-provider-acceptance-production-promotion-review",
        "label": "审查 trade_cal production freshness promotion",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_trade_cal_production_promotion_review_pipeline",
        "external_call_policy": "local_trade_cal_production_promotion_review_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": [],
        "ltg": "LTG-01/LTG-11",
        "local_production_promotion_review_only": True,
        "requires_prior_task_type": "run_trade_cal_provider_acceptance_release_review",
        "requires_prior_provider_evidence": True,
        "requires_matching_remote_ci_green": True,
        "requires_user_confirmation": True,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_review": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "strict_closeout_ready_after_success": True,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_current_evidence_producer_cache_refresh_execution_request",
        "route": "POST /api/data-health/producer-cache-refresh-execution-request",
        "label": "生成 current evidence producer cache refresh 执行请求 ticket",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_producer_cache_refresh_execution_request_pipeline",
        "external_call_policy": "local_producer_cache_refresh_execution_request_no_write_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": [],
        "ltg": "LTG-01",
        "local_execution_request_only": True,
        "requires_current_readiness_scope_hash": True,
        "requires_user_confirmation": True,
        "target_local_task_route": "POST /api/data-health/producer-cache-refresh",
        "target_task_type": "run_current_evidence_producer_cache_refresh",
        "writes_snapshot_cache": False,
        "creates_task": False,
        "executes_local_refresh": False,
        "builds_missing_packets": False,
        "provider_execution_implemented": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_current_evidence_producer_cache_refresh",
        "route": "POST /api/data-health/producer-cache-refresh",
        "label": "执行 current evidence producer 本地 cache refresh",
        "output_packet_key": "command_center_3_data_health_timeline_cache",
        "button_gated": True,
        "current_backend": "local_producer_cache_refresh_sqlite_packet_writer",
        "external_call_policy": "local_sqlite_packet_write_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": [],
        "ltg": "LTG-01",
        "local_execution_request_only": False,
        "requires_prior_task_type": "run_current_evidence_producer_cache_refresh_execution_request",
        "requires_current_readiness_scope_hash": True,
        "requires_bound_scope_hash": True,
        "requires_user_confirmation": True,
        "target_local_task_route": "POST /api/data-health/producer-cache-refresh",
        "target_task_type": "run_current_evidence_producer_cache_refresh",
        "writes_snapshot_cache": False,
        "writes_local_sqlite_packets": True,
        "writes_parquet": False,
        "creates_task": True,
        "executes_local_refresh": True,
        "builds_missing_packets": True,
        "builds_missing_packets_from_local_snapshot_builder": True,
        "provider_execution_implemented": False,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "refresh_factor_data",
        "route": "POST /api/factor-quant/refresh-data",
        "label": "刷新因子数据",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "button_gated_tushare_pipeline",
        "external_call_policy": "button_gated_tushare_capable",
        "possible_external_sources": ["tushare"],
        "default_core_apis": ["daily", "daily_basic", "moneyflow"],
        "calendar_apis": ["trade_cal"],
        "optional_extended_apis": list(TUSHARE_OPTIONAL_EXTENDED_APIS),
        "parquet_enabled_apis": ["daily", "daily_basic", "moneyflow", "trade_cal"],
        "extended_validation_scope": "refresh_data_delegates_to_tushare_task_pipeline",
        "api_validation_matrix_policy": "selected APIs use call_ledger; unselected APIs are capability matrix only and must not be treated as verified.",
        "api_acceptance_audit_contract": "delegated Tushare refresh packet must expose the same call_ledger semantic audit before any result is accepted.",
        "failure_mode_qa_contract": "delegated Tushare refresh packet must expose failure_mode_qa_contract; it is a local classifier, not provider-backed production acceptance.",
        "failure_mode_qa_is_provider_acceptance": False,
        "request_parameter_qa_contract": "delegated Tushare refresh packet must expose request_parameter_qa_contract; it is a local parameter contract, not provider-backed production acceptance.",
        "request_parameter_qa_is_provider_acceptance": False,
        "provider_target_sample_plan_contract": "delegated Tushare refresh packet must expose provider_target_sample_plan_contract; it is a target sample plan, not provider-backed production acceptance.",
        "provider_target_sample_plan_is_provider_acceptance": False,
        "provider_target_sample_acceptance_contract": "delegated Tushare refresh packet must expose explicit target-sample acceptance evidence review when requested; it is not full-interface production acceptance.",
        "provider_target_sample_acceptance_mode": "provider_target_sample_acceptance",
        "provider_target_sample_acceptance_mode_requires_explicit_payload": True,
        "provider_target_sample_acceptance_is_full_interface_acceptance": False,
        "provider_evidence_gap_audit_contract": "delegated Tushare refresh packet must expose provider_evidence_gap_audit; it is a local gap ledger, not provider-backed production acceptance.",
        "provider_evidence_gap_audit_is_provider_acceptance": False,
        "provider_target_sample_execution_recipe": "delegated Tushare refresh packet must expose provider_target_sample_execution_recipe; it is a local ordered recipe, not provider-backed production acceptance.",
        "provider_target_sample_execution_recipe_is_provider_acceptance": False,
        "provider_target_sample_execution_recipe_creates_task": False,
        "tushare_durable_evidence_recipe": "delegated Tushare refresh packet must expose tushare_durable_evidence_recipe; it is a local durable checklist, not provider-backed production acceptance.",
        "tushare_durable_evidence_recipe_is_provider_acceptance": False,
        "tushare_durable_evidence_recipe_creates_task": False,
        "full_interface_acceptance_done": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "command_center_live_bootstrap",
        "route": "POST /api/bootstrap/live-startup",
        "label": "创建 Command Center 3 live_light 启动任务",
        "output_packet_key": "command_center_live_bootstrap_packet",
        "button_gated": True,
        "current_backend": "local_bootstrap_pipeline_skeleton",
        "external_call_policy": "mode_gated_live_light_bootstrap_current_no_provider_execution",
        "possible_external_sources": ["tushare"],
        "optional_downstream_external_sources": ["deepseek"],
        "optional_downstream_task_types": ["run_deepseek_factor_explanation"],
        "runtime_modes": ["cache_only", "manual", "live_light", "live_full"],
        "default_mode": "cache_only",
        "live_light_default_enabled": False,
        "local_task_skeleton_implemented": True,
        "bootstrap_plan_skeleton_implemented": True,
        "model_ledger_preview_implemented": True,
        "bootstrap_stage_schema_version": "command_center_live_bootstrap_stage_plan.v1",
        "bootstrap_model_ledger_schema_version": "command_center_live_bootstrap_model_ledger_preview.v1",
        "provider_execution_implemented": False,
        "tushare_execution_implemented": False,
        "deepseek_execution_implemented": False,
        "rate_limit_enforced": True,
        "symbol_limit_default": 20,
        "rate_limit_seconds_default": 600,
        "default_core_apis": ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"],
        "staged_optional_domains": ["margin", "limit_emotion", "chip", "dragon_tiger", "disclosure", "hard_risk"],
        "deepseek_after_data_ready_only": True,
        "same_input_hash_deduplicated": True,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "page_render_creates_task_default": False,
        "full_pool_on_open_allowed": False,
        "github_probe_on_open_allowed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "command_center_live_bootstrap_provider_model_acceptance_dry_run",
        "route": "POST /api/bootstrap/provider-model-acceptance-dry-run",
        "label": "生成 live_light provider/model acceptance dry-run",
        "output_packet_key": "command_center_live_bootstrap_provider_model_acceptance_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_acceptance_dry_run_pipeline_no_provider_or_model_call",
        "external_call_policy": "local_acceptance_dry_run_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "runtime_modes": ["cache_only", "manual", "live_light"],
        "default_mode": "cache_only",
        "acceptance_runbook_consumed": True,
        "allowed_dry_run_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
        "unselected_apis_are_not_verified": True,
        "ignored_apis_reported": True,
        "requires_user_approval_flag": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "token_key_exposure_allowed": False,
        "provider_execution_implemented": False,
        "tushare_execution_implemented": False,
        "deepseek_execution_implemented": False,
        "model_execution_implemented": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "page_render_creates_task_default": False,
        "github_probe_on_open_allowed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "command_center_live_bootstrap_provider_model_execution_request",
        "route": "POST /api/bootstrap/provider-model-execution-request",
        "label": "生成 live_light provider/model execution-request ticket",
        "output_packet_key": "command_center_live_bootstrap_provider_model_execution_request_packet",
        "button_gated": True,
        "current_backend": "local_execution_request_receipt_pipeline_no_provider_or_model_call",
        "external_call_policy": "local_execution_request_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "runtime_modes": ["manual", "live_light"],
        "requires_latest_acceptance_dry_run": True,
        "requires_scope_hash_match": True,
        "requires_user_confirmation": True,
        "requires_credential_preflight_ready": True,
        "execution_request_only": True,
        "creates_provider_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "page_render_creates_task_default": False,
        "github_probe_on_open_allowed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tushare_deepseek_linkage_review",
        "route": "POST /api/migration/tushare-deepseek-linkage-review",
        "label": "审查 Tushare / DeepSeek 联动边界",
        "output_packet_key": "command_center_3_migration_status",
        "button_gated": True,
        "current_backend": "local_tushare_deepseek_linkage_review_pipeline",
        "external_call_policy": "local_tushare_deepseek_linkage_review_no_provider_or_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "ltg": "LTG-02/LTG-07/LTG-11/LTG-12/LTG-13",
        "local_review_only": True,
        "mode_layer_review": True,
        "requires_user_confirmation": True,
        "review_layers": [
            "cache_render_startup",
            "post_task_creation",
            "provider_model_execution_inside_task",
            "production_promotion_evidence",
        ],
        "creates_provider_task": False,
        "creates_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "production_quant_projection_complete": False,
        "production_promotion_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "github_probe_on_open_allowed": False,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_light",
        "route": "POST /api/factor-quant/run-light",
        "label": "运行 light mode 因子计算",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_light_pipeline",
        "external_call_policy": "local_cache_only_current_or_local_universe_seed",
        "possible_external_sources": [],
        "universe_modes": ["current_target", "watchlist", "custom_pool"],
        "future_universe_modes": ["full_pool"],
        "factor_universe_contract_status": "current_target_or_local_universe_seed_pipeline",
        "local_rank_zscore_seed_supported": True,
        "local_rank_zscore_seed_is_provider_acceptance": False,
        "production_factor_universe_complete": False,
        "full_pool_requires_worker": True,
        "frontend_computes_rank_zscore": False,
        "page_render_starts_full_pool": False,
        "partial_pool_is_full_market_proof": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_universe_research_plan",
        "route": "POST /api/factor-quant/universe-research-plan",
        "label": "生成 Factor universe 研究读取计划",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_storage_query_read_plan_pipeline",
        "external_call_policy": "local_storage_query_contract_only_no_external_call",
        "possible_external_sources": [],
        "universe_modes": ["watchlist", "custom_pool", "full_pool"],
        "storage_query_contract_consumed": True,
        "worker_task_consumption_plan_ready": True,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "full_pool_requires_worker": True,
        "frontend_computes_rank_zscore": False,
        "page_render_starts_full_pool": False,
        "partial_pool_is_full_market_proof": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_universe_worker_batch_dry_run",
        "route": "POST /api/factor-quant/universe-worker-batch-dry-run",
        "label": "生成 Factor universe worker-batch dry-run ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_universe_worker_batch_dry_run_pipeline",
        "external_call_policy": "local_worker_batch_dry_run_no_worker_provider_or_model_call",
        "possible_external_sources": [],
        "ltg": "LTG-04/LTG-11",
        "local_dry_run_only": True,
        "target_worker_task_route": "POST /api/factor-quant/universe-worker-batch-research",
        "target_acceptance_mode": "worker_backed_factor_universe_batch_research",
        "universe_modes": ["watchlist", "custom_pool", "full_pool"],
        "required_datasets": ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"],
        "required_stages": ["storage_read_plan", "worker_batch_scope", "cross_sectional_rank", "zscore", "neutralization", "factor_combination", "result_summary", "promotion_review"],
        "minimum_symbol_count_for_watchlist_or_custom_pool": 20,
        "symbol_limit_default": 500,
        "requires_user_approval_flag": True,
        "scope_hash_ticket": True,
        "worker_execution_implemented": False,
        "worker_batch_executed": False,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "production_factor_universe_complete": False,
        "full_pool_requires_worker": True,
        "frontend_computes_rank_zscore": False,
        "page_render_starts_full_pool": False,
        "partial_pool_is_full_market_proof": False,
        "cache_get_external_calls": False,
        "react_render_direct_worker_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_universe_worker_batch_execution_request",
        "route": "POST /api/factor-quant/universe-worker-batch-execution-request",
        "label": "生成 Factor universe worker-batch 执行请求 ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_universe_worker_batch_execution_request_pipeline",
        "external_call_policy": "local_execution_request_no_worker_provider_or_model_call",
        "possible_external_sources": [],
        "ltg": "LTG-04/LTG-06/LTG-11",
        "local_execution_request_only": True,
        "requires_prior_task_type": "run_factor_universe_worker_batch_dry_run",
        "requires_bound_scope_hash": True,
        "target_worker_task_route": "POST /api/factor-quant/universe-worker-batch-research",
        "target_worker_task_type": "run_factor_universe_worker_batch_research",
        "target_acceptance_mode": "worker_backed_factor_universe_batch_research",
        "universe_modes": ["watchlist", "custom_pool", "full_pool"],
        "required_datasets": ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"],
        "required_stages": ["storage_read_plan", "worker_batch_scope", "cross_sectional_rank", "zscore", "neutralization", "factor_combination", "result_summary", "promotion_review"],
        "requires_user_approval_flag": True,
        "creates_worker_task": False,
        "starts_worker": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "worker_execution_implemented": False,
        "worker_task_executed_by_request": False,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": False,
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "production_factor_universe_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_worker_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_universe_worker_batch_research",
        "route": "POST /api/factor-quant/universe-worker-batch-research",
        "label": "执行 Factor universe worker-batch 本地证据或记录本地收据",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_universe_worker_batch_research_receipt_or_execution_evidence_pipeline",
        "external_call_policy": "local_worker_batch_evidence_no_celery_redis_provider_or_model_call",
        "possible_external_sources": [],
        "ltg": "LTG-04/LTG-06/LTG-11",
        "local_worker_research_receipt_only": False,
        "supports_local_worker_execution_evidence": True,
        "requires_prior_task_type": "run_factor_universe_worker_batch_execution_request",
        "requires_bound_scope_hash": True,
        "requires_user_approval_flag": True,
        "creates_worker_task": True,
        "starts_worker": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "worker_execution_implemented": True,
        "worker_process_started": False,
        "worker_task_executed_by_request": True,
        "storage_read_executed": True,
        "large_universe_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": True,
        "zscore_done": True,
        "neutralization_done": False,
        "factor_combination_research_done": True,
        "result_summary_persisted": True,
        "production_factor_universe_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_worker_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_test_provider_small_pool_acceptance_dry_run",
        "route": "POST /api/factor-quant/provider-small-pool-dry-run",
        "label": "生成 Factor Test provider 小股票池验收 dry-run ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_test_provider_small_pool_acceptance_dry_run_pipeline",
        "external_call_policy": "local_acceptance_dry_run_no_provider_or_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-03/LTG-11",
        "local_dry_run_only": True,
        "target_provider_task_route": "future POST /api/factor-quant/provider-small-pool-acceptance",
        "target_acceptance_mode": "provider_backed_factor_test_small_pool_validation",
        "minimum_symbol_count": 5,
        "symbol_limit_default": 20,
        "minimum_window_days": 60,
        "required_datasets": ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"],
        "required_metrics": ["ic", "rank_ic", "icir", "group_return", "top_bottom", "max_drawdown", "neutral_ic", "out_of_sample_decay", "cost_model"],
        "requires_user_approval_flag": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "scope_hash_ticket": True,
        "provider_execution_implemented": False,
        "provider_backed_small_pool_validation_done": False,
        "production_factor_test_validation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_test_provider_small_pool_execution_request",
        "route": "POST /api/factor-quant/provider-small-pool-execution-request",
        "label": "生成 Factor Test provider 小股票池执行请求 ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_test_provider_small_pool_execution_request_pipeline",
        "external_call_policy": "local_execution_request_no_provider_or_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-03/LTG-02/LTG-11",
        "local_execution_request_only": True,
        "requires_prior_task_type": "run_factor_test_provider_small_pool_acceptance_dry_run",
        "requires_bound_scope_hash": True,
        "target_provider_task_route": "future POST /api/factor-quant/provider-small-pool-acceptance",
        "target_provider_task_type": "run_factor_test_provider_small_pool_acceptance",
        "target_acceptance_mode": "provider_backed_factor_test_small_pool_validation",
        "required_datasets": ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"],
        "required_metrics": [
            "ic",
            "rank_ic",
            "icir",
            "group_return",
            "top_bottom",
            "max_drawdown",
            "neutral_ic",
            "out_of_sample_decay",
            "cost_model",
        ],
        "requires_user_approval_flag": True,
        "creates_provider_task": False,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_small_pool_validation_done": False,
        "production_factor_test_validation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_test_provider_small_pool_acceptance",
        "route": "POST /api/factor-quant/provider-small-pool-acceptance",
        "label": "记录 Factor Test provider 小股票池验收授权闸门",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_factor_test_provider_small_pool_acceptance_gate_pipeline_no_provider_execution",
        "external_call_policy": "local_acceptance_gate_requires_separate_live_provider_authorization_no_provider_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare"],
        "ltg": "LTG-03/LTG-02/LTG-11",
        "local_acceptance_gate_only": True,
        "requires_prior_task_type": "run_factor_test_provider_small_pool_execution_request",
        "requires_bound_scope_hash": True,
        "target_acceptance_mode": "provider_backed_factor_test_small_pool_validation",
        "required_datasets": ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"],
        "required_metrics": [
            "ic",
            "rank_ic",
            "icir",
            "group_return",
            "top_bottom",
            "max_drawdown",
            "neutral_ic",
            "out_of_sample_decay",
            "cost_model",
        ],
        "requires_user_approval_flag": True,
        "requires_separate_live_provider_authorization": True,
        "creates_provider_task": False,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_call_ledger_evidence_done": False,
        "provider_backed_small_pool_validation_done": False,
        "production_factor_test_validation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_test_provider_industry_membership",
        "route": "POST /api/factor-quant/provider-industry-membership",
        "label": "采集 Factor Test 申万行业历史成分 raw evidence",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "scope_bound_index_member_all_provider_executor_pit_promotion_fail_closed",
        "external_call_policy": "exact_scope_three_flag_user_authorized_tushare_index_member_all_only",
        "possible_external_sources": ["tushare"],
        "ltg": "LTG-03/LTG-11/LTG-12",
        "requires_prior_task_type": "run_factor_test_provider_small_pool_acceptance",
        "requires_bound_scope_hash": True,
        "requires_bound_source_acceptance_scope_hash": True,
        "requires_user_approval_flag": True,
        "requires_live_provider_authorization_flag": True,
        "requires_provider_run_approval_flag": True,
        "allowed_tushare_apis": ["index_member_all"],
        "maximum_symbol_count": 5,
        "expected_provider_call_count": 10,
        "provider_query_is_new_values": ["Y", "N"],
        "provider_output_fields": [
            "l1_code",
            "l1_name",
            "l2_code",
            "l2_name",
            "l3_code",
            "l3_name",
            "ts_code",
            "name",
            "in_date",
            "out_date",
            "is_new",
        ],
        "provider_out_date_endpoint_semantics": "provider_documentation_unspecified",
        "persists_raw_rows_and_pit_provenance": True,
        "pit_promotion_fail_closed": True,
        "provider_execution_implemented": True,
        "provider_backed_pit_industry_membership_done": False,
        "production_factor_test_validation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_deepseek_factor_explanation",
        "route": "POST /api/factor-quant/deepseek-explain",
        "label": "DeepSeek 整理因子解释",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "guarded_prompt_or_payload_sanitizer",
        "external_call_policy": "governed_manual_or_auto_after_task_deepseek_capable_current_no_model_call",
        "possible_external_sources": ["deepseek"],
        "explanation_modes": ["manual_only", "auto_after_task", "disabled"],
        "default_explanation_mode": "manual_only",
        "auto_after_task_default": False,
        "cache_key_fields": ["module", "ts_code", "universe", "trade_date", "input_hash", "model_name", "prompt_version"],
        "same_input_hash_deduplicated": True,
        "deepseek_model_strategy_purpose": "factor_explain",
        "deepseek_model_config_keys": list(DEEPSEEK_MODEL_CONFIG_KEYS["factor_explain"]),
        "deepseek_model_source": "config.get_deepseek_model('factor_explain')",
        "does_not_hardcode_deepseek_model": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_deepseek_provider_benchmark_scope_ticket",
        "route": "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket",
        "label": "生成 DeepSeek provider benchmark scope ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_deepseek_provider_benchmark_scope_ticket_pipeline",
        "external_call_policy": "local_scope_ticket_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["deepseek"],
        "ltg": "LTG-07/LTG-11",
        "local_scope_ticket_only": True,
        "target_provider_task_route": "POST /api/factor-quant/deepseek-provider-benchmark",
        "target_acceptance_mode": "provider_backed_deepseek_json_stability_benchmark",
        "minimum_sample_count": 40,
        "required_json_success_rate": 0.9,
        "max_retry_per_sample": 2,
        "required_response_format": "json_object",
        "required_model_ledger_fields": [
            "model_used",
            "status",
            "token_usage",
            "parse_status",
            "cache_hit_or_miss",
            "input_hash",
            "output_hash",
        ],
        "requires_user_approval_flag": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "scope_hash_ticket": True,
        "model_execution_implemented": False,
        "provider_benchmark_done": False,
        "provider_response_format_enforced": False,
        "bounded_retry_repair_executed": False,
        "token_budget_cost_evidence_complete": False,
        "auto_after_task_production_ready": False,
        "production_deepseek_explanation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_model_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
    },
    {
        "task_type": "refresh_margin_etf_local_packets",
        "route": "POST /api/market/margin-etf-local-refresh",
        "label": "刷新/回放 ETF 与融资本地 packet",
        "output_packet_key": "command_center_margin_etf_refresh_receipt",
        "button_gated": True,
        "current_backend": "local_margin_etf_packet_replay_pipeline",
        "external_call_policy": "local_packet_replay_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "ltg": "LTG-05/LTG-10/LTG-12",
        "local_packet_replay_only": True,
        "source_packet_keys": ["command_center_etf_packet", "command_center_margin_packet"],
        "cache_get_external_calls": False,
        "react_render_direct_provider_calls": False,
        "provider_refresh_implemented": False,
        "model_execution_implemented": False,
        "degraded_reason_required_when_packets_missing": True,
        "does_not_build_missing_packets_from_external_sources": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "call_ledger_required": True,
    },
    {
        "task_type": "run_deepseek_provider_benchmark_execution_request",
        "route": "POST /api/factor-quant/deepseek-provider-benchmark-execution-request",
        "label": "生成 DeepSeek provider benchmark execution request ticket",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_deepseek_provider_benchmark_execution_request_pipeline",
        "external_call_policy": "local_execution_request_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["deepseek"],
        "ltg": "LTG-07/LTG-11",
        "requires_prior_scope_ticket": True,
        "local_execution_request_only": True,
        "target_model_task_route": "POST /api/factor-quant/deepseek-provider-benchmark",
        "target_model_task_type": "run_deepseek_provider_benchmark",
        "target_acceptance_mode": "provider_backed_deepseek_json_stability_benchmark",
        "requires_user_approval_flag": True,
        "scope_hash_bound_to_latest_ticket": True,
        "model_task_created": False,
        "model_execution_implemented": False,
        "provider_benchmark_done": False,
        "model_ledger_evidence_done": False,
        "provider_response_format_enforced": False,
        "bounded_retry_repair_executed": False,
        "token_budget_cost_evidence_complete": False,
        "production_deepseek_explanation_complete": False,
        "cache_get_external_calls": False,
        "react_render_direct_model_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
    },
    {
        "task_type": "run_deepseek_provider_benchmark",
        "route": "POST /api/factor-quant/deepseek-provider-benchmark",
        "label": "执行 governed DeepSeek provider benchmark",
        "output_packet_key": "command_center_deepseek_provider_benchmark_current",
        "button_gated": True,
        "current_backend": "guarded_deepseek_provider_benchmark_executor",
        "external_call_policy": "explicit_post_scope_bound_deepseek_only",
        "possible_external_sources": ["deepseek"],
        "ltg": "LTG-07/LTG-11",
        "requires_prior_scope_ticket": True,
        "requires_prior_execution_request": True,
        "requires_user_approval_flag": True,
        "requires_provider_run_approval_flag": True,
        "fixed_sample_count": 40,
        "required_json_success_rate": 0.9,
        "required_response_format": "json_object",
        "max_retry_per_sample": 2,
        "max_network_attempts_per_sample": 3,
        "timeout_seconds": 25,
        "sdk_max_retries": 0,
        "scope_contract_version": "factor_deepseek_provider_benchmark_contract.v4",
        "scope_contract_exact_binding_required": True,
        "scope_binding_fields": [
            "model",
            "sample_ids_and_hashes",
            "retry_and_timeout",
            "output_schema_and_prompt_versions",
            "system_prompt_sha256",
            "exact_base_url_and_temperature",
            "sdk_max_retries_zero",
            "ledger_contract",
            "token_cost_policy",
            "global_deadline",
            "single_use_authorization_nonce",
        ],
        "global_deadline_seconds": 900,
        "post_response_global_deadline_enforced": True,
        "approval_nonce_enforced": True,
        "authorization_nonce_caller_generated": True,
        "authorization_nonce_raw_persisted": False,
        "preflight_failure_consumes_nonce": True,
        "approval_replay_boundary": "single_use_sqlite_compare_and_consume_before_http",
        "explicit_http_client_transport_is_test_only": True,
        "injected_model_call_transport_is_test_only": True,
        "official_sdk_internal_construction_required_for_production": True,
        "production_packet_external_finalizer_available": False,
        "atomic_execution_event_required": True,
        "v1_task_event_nonce_packet_four_way_binding_required": True,
        "model_output_closed_enums_only": True,
        "deterministic_local_summary_only": True,
        "last_good_preserved_on_failure": True,
        "synthetic_evidence_closes_ltg07": False,
        "provider_benchmark_done_only_after_real_success": True,
        "cache_get_external_calls": False,
        "react_render_direct_model_calls": False,
        "startup_model_calls": False,
        "typing_model_calls": False,
        "call_ledger_required": True,
        "server_secret_values_exposed": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
    },
    {
        "task_type": "build_next_session_projection",
        "route": "POST /api/next-session/generate",
        "label": "生成次日操作图谱",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_next_session_browser_qa_review",
        "route": "POST /api/next-session/browser-qa-review",
        "label": "审查次日图谱 browser QA 本地证据",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ignored_artifact_review_only_no_browser_no_external_call",
        "possible_external_sources": [],
        "browser_qa_review_only": True,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "reads_ignored_local_reports_only": True,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_next_session_streamlit_parity_review",
        "route": "POST /api/next-session/streamlit-parity-review",
        "label": "审查次日图谱信号/能力 parity 同包证据",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_same_packet_no_feature_loss_review_only_no_streamlit_no_browser_no_external_call",
        "possible_external_sources": [],
        "streamlit_parity_review_only": True,
        "opens_streamlit": False,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "same_packet_no_loss_review": True,
        "streamlit_reference_captured": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_next_session_production_promotion_review",
        "route": "POST /api/next-session/production-promotion-review",
        "label": "审查次日图谱 production promotion 本地阻断",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_promotion_blocker_review_only_no_streamlit_no_browser_no_external_call",
        "possible_external_sources": [],
        "production_promotion_review_only": True,
        "opens_streamlit": False,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "requires_browser_qa_review": True,
        "requires_streamlit_parity_review": True,
        "requires_durable_evidence_recipe": True,
        "requires_durable_ci_or_release_evidence": True,
        "ready_to_mark_production_replacement_complete": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_package_artifact_review",
        "route": "POST /api/desktop/tauri-package-artifact-review",
        "label": "审查 Tauri release binary 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ignored_release_binary_artifact_review_only_no_build_no_runtime_no_external_call",
        "possible_external_sources": [],
        "artifact_review_only": True,
        "runs_build": False,
        "opens_packaged_app": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_packaged_runtime_launch_review",
        "route": "POST /api/desktop/tauri-packaged-runtime-launch-review",
        "label": "审查 Tauri packaged app 启动 smoke 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_packaged_app_launch_smoke_review_only_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "launch_review_only": True,
        "runs_build": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "backend_offline_ux_verified": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_backend_offline_packaged_ux_review",
        "route": "POST /api/desktop/tauri-backend-offline-packaged-ux-review",
        "label": "审查 Tauri packaged backend offline UX 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_packaged_backend_offline_ux_review_only_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "offline_ux_review_only": True,
        "runs_build": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "stores_screenshot_artifact": False,
        "stores_screenshot_hash_only": True,
        "backend_offline_ux_verified": True,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_backend_startup_runtime_review",
        "route": "POST /api/desktop/tauri-backend-startup-runtime-review",
        "label": "审查 Tauri packaged manual FastAPI runtime 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_manual_fastapi_packaged_runtime_review_only_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "backend_startup_runtime_review_only": True,
        "runs_build": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "stores_screenshot_artifact": False,
        "stores_screenshot_hash_only": True,
        "backend_startup_runtime_validated": True,
        "backend_sidecar_autostart_validated": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_config_log_runtime_review",
        "route": "POST /api/desktop/tauri-config-log-runtime-review",
        "label": "审查 Tauri packaged config/log runtime path 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_config_log_path_policy_review_only_no_secret_no_write_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "config_log_runtime_review_only": True,
        "runs_build": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "stores_screenshot_artifact": False,
        "stores_screenshot_hash_only": True,
        "config_log_runtime_paths_validated": True,
        "packaged_runtime_validated": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_signing_notarization_review",
        "route": "POST /api/desktop/tauri-signing-notarization-review",
        "label": "审查 Tauri signing/notarization gap 本地证据",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_codesign_spctl_gap_review_only_no_sign_no_notary_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "signing_notarization_gap_review_only": True,
        "runs_build": False,
        "runs_codesign": False,
        "runs_spctl": False,
        "runs_notarytool": False,
        "starts_fastapi": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "signing_notarization_done": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_tauri_production_package_promotion_review",
        "route": "POST /api/desktop/tauri-production-package-promotion-review",
        "label": "审查 Tauri production package promotion 本地阻断",
        "output_packet_key": "command_center_3_desktop_shell_preflight_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_tauri_production_package_promotion_review_only_no_build_no_runtime_no_external_call",
        "possible_external_sources": [],
        "production_package_promotion_review_only": True,
        "runs_build": False,
        "opens_packaged_app": False,
        "starts_fastapi": False,
        "runs_codesign": False,
        "runs_spctl": False,
        "runs_notarytool": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "production_package_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_streamlit_ordinary_workflow_parity_review",
        "route": "POST /api/legacy/ordinary-workflow-parity-review",
        "label": "审查 Streamlit ordinary workflow parity 本地证据",
        "output_packet_key": "command_center_3_legacy_bridge_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ordinary_workflow_parity_review_only_no_streamlit_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "ordinary_workflow_parity_review_only": True,
        "runs_streamlit": False,
        "runs_legacy_tools": False,
        "creates_tasks_from_get_cache": False,
        "removes_streamlit_fallback": False,
        "deletes_app_py": False,
        "provider_model_task_dispatched": False,
        "replacement_parity_complete": False,
        "candidate_radar_parity_complete": False,
        "streamlit_retirement_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_legacy_audit_observation_dry_run",
        "route": "POST /api/legacy/audit-observation-dry-run",
        "label": "记录 Legacy Bug / UX Audit 第一轮观察 dry-run",
        "output_packet_key": "command_center_3_legacy_audit_observation_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_legacy_audit_observation_receipt_no_streamlit_execution",
        "external_call_policy": "local_observation_dry_run_no_streamlit_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "first_round_observation_dry_run_only": True,
        "requires_safe_attachment_reference": True,
        "keep_promotion_allowed": False,
        "ordinary_entry_promotion_allowed": False,
        "streamlit_retirement_allowed": False,
        "runs_streamlit": False,
        "runs_legacy_tools": False,
        "creates_tasks_from_get_cache": False,
        "creates_followup_tasks": False,
        "removes_streamlit_fallback": False,
        "provider_model_task_dispatched": False,
        "production_evidence": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_streamlit_fallback_retirement_review",
        "route": "POST /api/legacy/fallback-retirement-review",
        "label": "审查 Streamlit fallback retirement 本地证据",
        "output_packet_key": "command_center_3_legacy_bridge_cache",
        "button_gated": True,
        "current_backend": "local_streamlit_fallback_retirement_review_pipeline",
        "external_call_policy": "local_fallback_retirement_review_only_no_streamlit_no_provider_model_github_trade_call",
        "possible_external_sources": [],
        "fallback_retirement_review_only": True,
        "requires_ordinary_workflow_parity_review": True,
        "runs_streamlit": False,
        "runs_legacy_tools": False,
        "creates_tasks_from_get_cache": False,
        "removes_streamlit_fallback": False,
        "deletes_app_py": False,
        "provider_model_task_dispatched": False,
        "ordinary_workflow_exit_complete": False,
        "streamlit_retirement_complete": False,
        "full_streamlit_removal_ready": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_quick_scan",
        "route": "POST /api/candidate-radar/scan-quick",
        "label": "运行下一票雷达 local scan",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "scan_modes": ["quick_cache_scan", "watchlist_scan", "custom_pool_scan", "full_pool_local_scan"],
        "future_scan_modes": ["full_pool_scan", "manual_deep_research"],
        "runtime_budget_contract_visible": True,
        "result_delta_clarity_contract_visible": True,
        "result_delta_clarity_is_previous_cache_diff": False,
        "result_delta_clarity_previous_cache_diff_supported": True,
        "result_delta_clarity_previous_cache_diff_requires_persisted_cache": True,
        "result_delta_clarity_is_browser_visual_qa": False,
        "sync_candidate_display_limit": 120,
        "local_pool_input_limit": 50,
        "large_universe_requires_worker": True,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_quant_projection",
        "route": "POST /api/candidate-radar/quant-projection",
        "label": "生成搜票 3.0 Tushare-first 量化推演任务",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "button_gated_search_quant_projection_chain",
        "external_call_policy": "button_confirmed_tushare_first_chain_deepseek_skipped_or_blocked",
        "possible_external_sources": ["tushare"],
        "future_external_sources": ["deepseek"],
        "scan_modes": ["search_quant_projection"],
        "local_receipt_only": False,
        "local_receipt_first": True,
        "symbol_validation_required": True,
        "user_approval_required": True,
        "confirmed_tushare_first_chain_supported": True,
        "tushare_first_requires_user_approval": True,
        "provider_model_route_requires_execution_request": True,
        "tushare_called_only_from_post_task": True,
        "deepseek_skipped_by_default": True,
        "deepseek_governed_executor_pending": True,
        "cache_ledger_packet_writeback_supported": True,
        "provider_model_pending": True,
        "tushare_called": False,
        "deepseek_called": False,
        "provider_execution_implemented": True,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_quant_projection_acceptance_dry_run",
        "route": "POST /api/candidate-radar/quant-projection-acceptance-dry-run",
        "label": "搜票量化推演 Tushare/DeepSeek 联动验收 dry-run",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_preflight_pipeline",
        "external_call_policy": "local_quant_projection_acceptance_dry_run_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "scan_modes": ["search_quant_projection"],
        "local_dry_run_only": True,
        "symbol_validation_required": True,
        "user_approval_required": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "allowed_tushare_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "tushare_called": False,
        "deepseek_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_quant_projection_execution_request",
        "route": "POST /api/candidate-radar/quant-projection-execution-request",
        "label": "搜票量化推演 provider/model execution request",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_execution_request_pipeline",
        "external_call_policy": "local_quant_projection_execution_request_no_provider_or_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "scan_modes": ["quant_projection_execution_request"],
        "local_execution_request_only": True,
        "user_approval_required": True,
        "requires_prior_task_type": "run_candidate_radar_quant_projection_acceptance_dry_run",
        "requires_bound_scope_hash": True,
        "requires_acceptance_scope_hash": True,
        "target_provider_model_task_route": "POST /api/candidate-radar/quant-projection-provider-model-acceptance",
        "target_provider_model_task_type": "run_candidate_radar_quant_projection_provider_model_acceptance",
        "allowed_tushare_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "creates_provider_model_task": False,
        "provider_model_task_executed_by_request": False,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_quant_projection_provider_model_acceptance",
        "route": "POST /api/candidate-radar/quant-projection-provider-model-acceptance",
        "label": "搜票量化推演 Tushare provider acceptance",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "button_gated_tushare_pipeline",
        "external_call_policy": "button_gated_tushare_light_provider_task_deepseek_skipped",
        "possible_external_sources": ["tushare"],
        "future_external_sources": ["deepseek"],
        "scan_modes": ["quant_projection_provider_model_acceptance"],
        "user_approval_required": True,
        "requires_prior_task_type": "run_candidate_radar_quant_projection_execution_request",
        "requires_bound_scope_hash": True,
        "requires_acceptance_scope_hash": True,
        "requires_quant_projection_scope_ticket": True,
        "allowed_tushare_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "creates_provider_model_task": False,
        "provider_execution_implemented": True,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "deepseek_skipped_by_default": True,
        "provider_call_ledger_evidence_done": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "tushare_called_only_from_post_task": True,
        "deepseek_called": False,
        "github_called": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "production_radar_replacement_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_provider_parity_dry_run",
        "route": "POST /api/candidate-radar/provider-parity-dry-run",
        "label": "下一票雷达 provider parity 验收 dry-run",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_preflight_pipeline",
        "external_call_policy": "local_provider_parity_dry_run_no_external_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "scan_modes": ["provider_parity_dry_run"],
        "local_dry_run_only": True,
        "user_approval_required": True,
        "server_secret_presence_check": "environment_key_membership_only_no_value_read",
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "provider_signal_groups": ["moneyflow", "dragon_tiger", "limit_emotion", "chip_radar", "hard_risk"],
        "requires_candidate_scope": True,
        "requires_legacy_parity_receipt": True,
        "requires_worker_full_pool_evidence": True,
        "requires_worker_deep_scan_evidence": True,
        "requires_browser_performance_evidence": True,
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "tushare_called": False,
        "deepseek_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_provider_parity_execution_request",
        "route": "POST /api/candidate-radar/provider-parity-execution-request",
        "label": "下一票雷达 provider parity execution request",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_provider_parity_execution_request_pipeline",
        "external_call_policy": "local_provider_parity_execution_request_no_provider_or_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["tushare", "deepseek"],
        "scan_modes": ["provider_parity_execution_request"],
        "local_execution_request_only": True,
        "user_approval_required": True,
        "requires_prior_task_type": "run_candidate_radar_provider_parity_dry_run",
        "requires_bound_scope_hash": True,
        "requires_acceptance_scope_hash": True,
        "requires_provider_parity_scope_ticket": True,
        "target_provider_task_route": "future POST /api/candidate-radar/provider-parity-acceptance",
        "target_provider_task_type": "future_run_candidate_radar_provider_parity_acceptance",
        "provider_signal_groups": ["moneyflow", "dragon_tiger", "limit_emotion", "chip_radar", "hard_risk"],
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "creates_provider_task": False,
        "provider_task_executed_by_request": False,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_provider_parity_acceptance",
        "route": "POST /api/candidate-radar/provider-parity-acceptance",
        "label": "下一票雷达 Tushare provider parity acceptance",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "button_gated_tushare_provider_parity_pipeline",
        "external_call_policy": "button_gated_tushare_light_provider_task_deepseek_skipped",
        "possible_external_sources": ["tushare"],
        "future_external_sources": ["deepseek"],
        "scan_modes": ["provider_parity_acceptance"],
        "user_approval_required": True,
        "requires_prior_task_type": "run_candidate_radar_provider_parity_execution_request",
        "requires_bound_scope_hash": True,
        "requires_acceptance_scope_hash": True,
        "requires_provider_parity_scope_ticket": True,
        "allowed_tushare_apis": ["trade_cal", "moneyflow", "top_list", "top_inst", "anns_d"],
        "call_ledger_required": True,
        "model_ledger_required_when_deepseek_enabled": True,
        "creates_provider_task": True,
        "provider_task_executed_by_request": True,
        "provider_execution_implemented": True,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "deepseek_skipped_by_default": True,
        "provider_call_ledger_evidence_done": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "tushare_called_only_from_post_task": True,
        "deepseek_called": False,
        "github_called": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_worker_execution_request",
        "route": "POST /api/candidate-radar/worker-execution-request",
        "label": "生成下一票雷达 worker execution request",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_worker_execution_request_pipeline",
        "external_call_policy": "local_worker_execution_request_no_worker_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "scan_modes": ["worker_execution_request"],
        "local_execution_request_only": True,
        "user_approval_required": True,
        "requires_worker_execution_recipe": True,
        "requires_worker_execution_scope_hash": True,
        "requires_local_full_pool_receipt": True,
        "requires_local_deep_scan_review": True,
        "requires_provider_parity_scope_ticket": True,
        "requires_quant_projection_scope_ticket_before_full_replacement": True,
        "target_worker_full_pool_route": "POST /api/candidate-radar/full-pool-worker-scan",
        "target_worker_deep_scan_route": "POST /api/candidate-radar/deep-scan-worker",
        "target_worker_full_pool_task_type": "run_candidate_radar_full_pool_worker_fallback",
        "target_worker_deep_scan_task_type": "run_candidate_radar_deep_scan_worker_fallback",
        "creates_worker_task": False,
        "worker_task_executed_by_request": False,
        "worker_execution_implemented": False,
        "worker_started": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_full_pool_worker_fallback",
        "route": "POST /api/candidate-radar/full-pool-worker-scan",
        "label": "运行下一票雷达 full-pool worker fallback",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_worker_fallback_pipeline",
        "external_call_policy": "local_worker_fallback_no_celery_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "scan_modes": ["full_pool_worker_fallback"],
        "local_worker_fallback_only": True,
        "user_approval_required": True,
        "requires_worker_execution_request": True,
        "requires_worker_execution_scope_hash": True,
        "requires_local_full_pool_receipt": True,
        "creates_worker_task": False,
        "worker_task_executed_by_fallback": False,
        "worker_execution_implemented": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "local_full_pool_worker_fallback_receipt_visible": True,
        "local_full_pool_worker_fallback_done": False,
        "production_full_pool_scan_done": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_promoted": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_deep_scan_worker_fallback",
        "route": "POST /api/candidate-radar/deep-scan-worker",
        "label": "运行下一票雷达 deep-scan worker fallback",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_worker_fallback_pipeline",
        "external_call_policy": "local_deep_scan_worker_fallback_no_celery_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "scan_modes": ["deep_scan_worker_fallback"],
        "local_worker_fallback_only": True,
        "user_approval_required": True,
        "requires_worker_execution_request": True,
        "requires_worker_execution_scope_hash": True,
        "requires_local_deep_scan_review": True,
        "creates_worker_task": False,
        "worker_task_executed_by_fallback": False,
        "worker_execution_implemented": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "local_deep_scan_worker_fallback_receipt_visible": True,
        "local_deep_scan_worker_fallback_done": False,
        "production_deep_scan_done": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "deepseek_model_ledger_complete": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_promoted": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_full_pool_plan",
        "route": "POST /api/candidate-radar/full-pool-plan",
        "label": "生成下一票雷达 full-pool 准备计划",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_full_pool_plan_only_no_external_call",
        "possible_external_sources": [],
        "scan_modes": ["full_pool_scan"],
        "plan_only": True,
        "full_pool_scan_done": False,
        "full_pool_validation_done": False,
        "result_delta_clarity_contract_visible": True,
        "result_delta_clarity_is_previous_cache_diff": False,
        "result_delta_clarity_previous_cache_diff_supported": True,
        "result_delta_clarity_previous_cache_diff_requires_persisted_cache": True,
        "result_delta_clarity_is_browser_visual_qa": False,
        "worker_task_consumption_plan_ready": True,
        "cache_get_external_calls": False,
        "page_render_starts_full_pool": False,
        "provider_refresh_executed": False,
        "candidate_scoring_executed": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_full_pool_local_scan",
        "route": "POST /api/candidate-radar/full-pool-local-scan",
        "label": "运行下一票雷达本地 full-pool",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_universe_execution_only_no_external_call",
        "possible_external_sources": [],
        "scan_modes": ["full_pool_local_scan"],
        "local_execution_only": True,
        "provider_backed_acceptance_done": False,
        "production_full_pool_scan_done": False,
        "worker_backed_execution_done": False,
        "full_pool_local_execution_receipt_visible": True,
        "result_delta_clarity_contract_visible": True,
        "cache_get_external_calls": False,
        "page_render_starts_full_pool": False,
        "provider_refresh_executed": False,
        "deepseek_called": False,
        "candidate_scoring_executed": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_full_market_production_acceptance",
        "route": "POST /api/worker/full-market-production-acceptance",
        "label": "运行下一票雷达全市场生产验收",
        "output_packet_key": "command_center_3_full_market_worker_production_acceptance",
        "button_gated": True,
        "current_backend": "external_redis_celery_candidate_batches",
        "external_call_policy": "explicit_post_real_redis_celery_only",
        "possible_external_sources": ["redis", "celery_worker"],
        "child_task_type": "run_candidate_radar_full_pool_local_scan",
        "requires_provider_current_and_last_good": True,
        "requires_stock_basic_current_listed_universe": True,
        "requires_trade_calendar_freshness": True,
        "requires_daily_minimum_sessions": 60,
        "requires_daily_basic_latest_session": True,
        "requires_moneyflow_minimum_sessions": 5,
        "rejects_eager_inproc_or_fake_transport": True,
        "writes_task_specific_results_only": True,
        "overwrites_candidate_global_cache": False,
        "supports_checkpoint_resume": True,
        "production_completion_requires_strict_readback": True,
        "cache_get_external_calls": False,
        "page_render_starts_full_pool": False,
        "provider_refresh_executed": False,
        "deepseek_called": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_full_market_factor_radar_map_reduce_request",
        "route": "POST /api/worker/full-market-factor-radar-map-reduce-request",
        "label": "记录 Factor 与 Radar 共享全市场 map/reduce 执行请求",
        "output_packet_key": "command_center_3_full_market_factor_radar_map_reduce_request",
        "button_gated": True,
        "current_backend": "local_scope_bound_execution_request_only",
        "external_call_policy": "no_provider_redis_celery_dispatch_from_request",
        "possible_external_sources": [],
        "requires_provider_current_and_last_good": True,
        "requires_minimum_universe_size": 3000,
        "requires_validated_trade_sessions": 90,
        "requires_effective_dated_industry_membership_digest": True,
        "shared_provider_reads": True,
        "factor_target_dataset": "full_market_factor_research_results",
        "radar_target_dataset": "full_market_candidate_radar_results",
        "factor_and_radar_outputs_are_independent": True,
        "external_trusted_lineage_runner_required": True,
        "provider_refresh_executed": False,
        "worker_execution_triggered": False,
        "production_complete": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_deep_scan_plan",
        "route": "POST /api/candidate-radar/deep-scan-plan",
        "label": "生成下一票雷达 deep-scan 准备清单",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_deep_scan_readiness_plan_only_no_external_call",
        "possible_external_sources": [],
        "scan_modes": ["deep_scan"],
        "plan_only": True,
        "deep_scan_done": False,
        "deep_scan_validation_done": False,
        "result_delta_clarity_contract_visible": True,
        "result_delta_clarity_is_previous_cache_diff": False,
        "result_delta_clarity_previous_cache_diff_supported": True,
        "result_delta_clarity_previous_cache_diff_requires_persisted_cache": True,
        "result_delta_clarity_is_browser_visual_qa": False,
        "worker_task_consumption_plan_ready": True,
        "cache_get_external_calls": False,
        "page_render_starts_deep_scan": False,
        "provider_refresh_executed": False,
        "deepseek_called": False,
        "candidate_scoring_executed": False,
        "feature_loss_gaps_visible": True,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_deep_scan_local_review",
        "route": "POST /api/candidate-radar/deep-scan-local-review",
        "label": "运行下一票雷达本地 deep-scan 审查",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_deep_scan_review_only_no_external_call",
        "possible_external_sources": [],
        "scan_modes": ["deep_scan_local_review"],
        "local_review_only": True,
        "deep_scan_done": False,
        "deep_scan_validation_done": False,
        "provider_backed_acceptance_done": False,
        "deepseek_called": False,
        "provider_refresh_executed": False,
        "worker_backed_execution_done": False,
        "deep_scan_local_review_receipt_visible": True,
        "result_delta_clarity_contract_visible": True,
        "cache_get_external_calls": False,
        "page_render_starts_deep_scan": False,
        "candidate_scoring_executed": False,
        "feature_loss_gaps_visible": True,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_browser_qa_review",
        "route": "POST /api/candidate-radar/browser-qa-review",
        "label": "审查下一票雷达 browser QA 本地证据",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ignored_artifact_review_only_no_browser_no_external_call",
        "possible_external_sources": [],
        "browser_qa_review_only": True,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "reads_ignored_local_reports_only": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "candidate_is_not_buy_instruction": True,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_production_replacement_review",
        "route": "POST /api/candidate-radar/production-replacement-review",
        "label": "审查下一票雷达生产替代本地证据",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_production_replacement_review_pipeline",
        "external_call_policy": "local_production_replacement_review_no_worker_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "local_review_only": True,
        "requires_legacy_parity_receipt": True,
        "requires_no_feature_loss_surface": True,
        "requires_local_full_pool_receipt": True,
        "requires_local_deep_scan_review": True,
        "requires_provider_parity_scope_ticket": True,
        "requires_worker_execution_request": True,
        "requires_quant_projection_execution_request": True,
        "requires_browser_qa_review": True,
        "requires_durable_evidence_recipe": True,
        "creates_worker_task": False,
        "worker_started": False,
        "worker_task_executed": False,
        "creates_provider_model_task": False,
        "provider_model_task_executed_by_review": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_promoted": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_production_promotion_dry_run",
        "route": "POST /api/candidate-radar/production-promotion-dry-run",
        "label": "生成下一票雷达 production promotion dry-run",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_production_promotion_dry_run_pipeline",
        "external_call_policy": "local_production_promotion_dry_run_no_worker_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "local_dry_run_only": True,
        "requires_production_replacement_review": True,
        "requires_production_replacement_review_scope_hash": True,
        "requires_operator_approval": True,
        "requires_worker_full_pool_evidence": True,
        "requires_worker_deep_scan_evidence": True,
        "requires_provider_backed_parity": True,
        "requires_deepseek_model_ledger_when_enabled": True,
        "requires_browser_visual_performance_promotion": True,
        "requires_legacy_retirement_review": True,
        "requires_durable_ci_or_release_evidence": True,
        "creates_worker_task": False,
        "worker_started": False,
        "worker_task_executed": False,
        "creates_provider_model_task": False,
        "provider_model_task_executed_by_dry_run": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "ready_to_mark_production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "deepseek_model_ledger_complete": False,
        "browser_visual_performance_promoted": False,
        "durable_ci_or_release_evidence_complete": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_production_promotion_review",
        "route": "POST /api/candidate-radar/production-promotion-review",
        "label": "审查下一票雷达 production promotion 本地边界",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_production_promotion_review_pipeline",
        "external_call_policy": "local_production_promotion_review_no_worker_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "local_review_only": True,
        "requires_production_replacement_review": True,
        "requires_production_promotion_dry_run": True,
        "requires_legacy_retirement_review": True,
        "requires_operator_approval": True,
        "requires_durable_evidence_recipe": True,
        "requires_production_stage_manifest": True,
        "requires_worker_full_pool_evidence": True,
        "requires_worker_deep_scan_evidence": True,
        "requires_provider_backed_parity": True,
        "requires_deepseek_model_ledger_when_enabled": True,
        "requires_browser_visual_performance_promotion": True,
        "requires_durable_ci_or_release_evidence": True,
        "creates_worker_task": False,
        "worker_started": False,
        "worker_task_executed": False,
        "creates_provider_model_task": False,
        "provider_model_task_executed_by_review": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "ready_to_mark_production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "deepseek_model_ledger_complete": False,
        "browser_visual_performance_promoted": False,
        "durable_ci_or_release_evidence_complete": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_candidate_radar_legacy_retirement_review",
        "route": "POST /api/candidate-radar/legacy-retirement-review",
        "label": "审查下一票雷达 legacy retirement 本地边界",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "button_gated": True,
        "current_backend": "local_legacy_retirement_review_pipeline",
        "external_call_policy": "local_legacy_retirement_review_no_worker_no_provider_no_model_call",
        "possible_external_sources": [],
        "future_external_sources": ["worker", "tushare", "deepseek"],
        "local_review_only": True,
        "requires_production_replacement_review": True,
        "requires_production_promotion_dry_run": True,
        "requires_operator_approval": True,
        "requires_durable_evidence_recipe": True,
        "requires_production_stage_manifest": True,
        "requires_no_feature_loss_surface": True,
        "requires_worker_full_pool_evidence": True,
        "requires_worker_deep_scan_evidence": True,
        "requires_provider_backed_parity": True,
        "requires_deepseek_model_ledger_when_enabled": True,
        "requires_browser_visual_performance_promotion": True,
        "requires_durable_ci_or_release_evidence": True,
        "creates_worker_task": False,
        "worker_started": False,
        "worker_task_executed": False,
        "creates_provider_model_task": False,
        "provider_model_task_executed_by_review": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "ready_to_retire_legacy": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "deepseek_model_ledger_complete": False,
        "browser_visual_performance_promoted": False,
        "durable_ci_or_release_evidence_complete": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "page_render_external_calls": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger_required": True,
        "server_secret_values_read": False,
        "env_key_names_exposed": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_motion_browser_qa_review",
        "route": "POST /api/audit/motion-browser-qa-review",
        "label": "审查 Command Center 3 motion browser QA 本地证据",
        "output_packet_key": "command_center_3_call_ledger_audit_cache",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ignored_artifact_review_only_no_browser_no_external_call",
        "possible_external_sources": [],
        "browser_qa_review_only": True,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "reads_ignored_local_reports_only": True,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_motion_production_promotion_dry_run",
        "route": "POST /api/audit/motion-production-promotion-dry-run",
        "label": "生成 Command Center 3 motion production promotion dry-run",
        "output_packet_key": "command_center_3_call_ledger_audit_cache",
        "button_gated": True,
        "current_backend": "local_preflight_pipeline",
        "external_call_policy": "local_motion_production_promotion_dry_run_no_browser_no_external_call",
        "possible_external_sources": [],
        "local_dry_run_only": True,
        "browser_qa_review_required": True,
        "visual_promotion_required": True,
        "performance_promotion_required": True,
        "durable_ci_evidence_required": True,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "reads_ignored_local_reports_only": True,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_motion_visual_performance_promotion_review",
        "route": "POST /api/audit/motion-visual-performance-promotion-review",
        "label": "审查 Command Center 3 motion visual/performance 本地推广证据",
        "output_packet_key": "command_center_3_call_ledger_audit_cache",
        "button_gated": True,
        "current_backend": "local_visual_performance_promotion_review_pipeline",
        "external_call_policy": "local_motion_visual_performance_review_no_browser_no_ci_no_github",
        "possible_external_sources": [],
        "local_review_only": True,
        "browser_qa_review_required": True,
        "promotion_dry_run_required": True,
        "visual_promotion_reviewed": True,
        "performance_promotion_reviewed": True,
        "reduced_motion_promotion_reviewed": True,
        "durable_ci_evidence_required": True,
        "opens_browser": False,
        "starts_servers": False,
        "writes_artifacts": False,
        "reads_ignored_local_reports_only": True,
        "github_called": False,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_artifact_cleanup_dry_run",
        "route": "POST /api/storage/artifact-hygiene/dry-run",
        "label": "生成 Storage artifact cleanup dry-run",
        "output_packet_key": "command_center_3_storage_artifact_cleanup_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_dry_run_no_delete_no_external_call",
        "possible_external_sources": [],
        "cleanup_policy": "dry_run_only_no_delete",
        "artifact_cleanup_review_contract_visible": True,
        "manual_delete_requires_separate_approval": True,
        "cleanup_review_is_not_delete_execution": True,
        "safe_delete_command_generated": False,
        "production_cleanup_complete": False,
        "cache_get_external_calls": False,
        "delete_files_on_post": False,
        "reads_file_payloads": False,
        "reads_env_files": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_schema_validation_dry_run",
        "route": "POST /api/storage/schema-validation/dry-run",
        "label": "运行 Storage schema validation dry-run",
        "output_packet_key": "command_center_3_storage_schema_validation_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_schema_metadata_only_no_external_call",
        "possible_external_sources": [],
        "validation_policy": "dry_run_only_no_migration_no_parquet_write",
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "schema_migration_executed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_backtest_results_schema_seed",
        "route": "POST /api/storage/backtest-results/schema-seed",
        "label": "写入 backtest_results 空 schema seed",
        "output_packet_key": "command_center_3_storage_backtest_results_schema_seed_packet",
        "button_gated": True,
        "current_backend": "local_schema_seed_pipeline",
        "external_call_policy": "confirm_gated_local_backtest_results_zero_row_schema_seed_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "schema_seed_policy": "confirm_gated_zero_row_parquet_schema_only_no_mock_backtest_result",
        "target_dataset": "backtest_results",
        "requires_confirm_schema_seed": True,
        "writes_parquet_on_post": True,
        "writes_only_ignored_local_parquet": True,
        "writes_backtest_result_rows": False,
        "mock_backtest_result_written": False,
        "writes_manifest_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_schema_validation_acceptance",
        "route": "POST /api/storage/schema-validation/acceptance",
        "label": "验收 Storage physical schema metadata",
        "output_packet_key": "command_center_3_storage_schema_validation_acceptance_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_schema_metadata_acceptance_only_no_external_call",
        "possible_external_sources": [],
        "validation_policy": "acceptance_only_no_migration_no_parquet_write",
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "schema_migration_executed": False,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_schema_migration_execution",
        "route": "POST /api/storage/schema-migration/execute",
        "label": "记录 Storage schema migration no-op evidence",
        "output_packet_key": "command_center_3_storage_schema_migration_execution_packet",
        "button_gated": True,
        "current_backend": "local_schema_migration_execution_pipeline",
        "external_call_policy": "confirm_gated_local_schema_migration_noop_evidence_no_external_call",
        "possible_external_sources": [],
        "validation_policy": "noop_verified_only_no_parquet_rewrite_no_manifest_write",
        "requires_confirm_schema_migration_execution": True,
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "schema_migration_executed": True,
        "schema_migration_rewrite_executed": False,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_dataset_version_manifest_dry_run",
        "route": "POST /api/storage/dataset-version-manifest/dry-run",
        "label": "生成 Storage dataset version manifest dry-run",
        "output_packet_key": "command_center_3_storage_dataset_version_manifest_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_manifest_write_plan_only_no_external_call",
        "possible_external_sources": [],
        "manifest_policy": "dry_run_only_no_manifest_write_no_parquet_payload_read",
        "cache_get_external_calls": False,
        "writes_manifest_on_post": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "manifest_write_executed": False,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_dataset_version_manifest_review",
        "route": "POST /api/storage/dataset-version-manifest/review",
        "label": "审查 Storage dataset version manifest 写入边界",
        "output_packet_key": "command_center_3_storage_dataset_version_manifest_review_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_manifest_review_only_no_external_call",
        "possible_external_sources": [],
        "manifest_policy": "review_only_no_manifest_write_no_parquet_payload_read",
        "cache_get_external_calls": False,
        "writes_manifest_on_post": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "manifest_write_executed": False,
        "schema_migration_executed": False,
        "production_storage_complete": False,
        "requires_separate_manifest_write": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_dataset_version_manifest_write",
        "route": "POST /api/storage/dataset-version-manifest/write",
        "label": "写入 Storage dataset version manifest",
        "output_packet_key": "command_center_3_storage_dataset_version_manifest_write_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_manifest_write_only_no_external_call",
        "possible_external_sources": [],
        "manifest_policy": "button_gated_local_manifest_write_no_parquet_payload_read",
        "cache_get_external_calls": False,
        "writes_manifest_on_post": True,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "requires_confirm_manifest_write": True,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_dataset_version_manifest_validate",
        "route": "POST /api/storage/dataset-version-manifest/validate",
        "label": "验证 Storage dataset version manifest",
        "output_packet_key": "command_center_3_storage_dataset_version_manifest_validate_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_manifest_validate_only_no_external_call",
        "possible_external_sources": [],
        "manifest_policy": "validate_only_no_manifest_write_no_parquet_payload_read",
        "cache_get_external_calls": False,
        "writes_manifest_on_post": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "manifest_write_executed": False,
        "requires_prior_manifest_write": True,
        "requires_separate_production_promotion": True,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_partition_migration_dry_run",
        "route": "POST /api/storage/partition-migration/dry-run",
        "label": "生成 Storage partition migration dry-run",
        "output_packet_key": "command_center_3_storage_partition_migration_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_partition_plan_only_no_external_call",
        "possible_external_sources": [],
        "partition_policy": "dry_run_only_no_partition_write_no_migration",
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "partition_migration_executed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_partition_migration_execution",
        "route": "POST /api/storage/partition-migration/execute",
        "label": "执行 Storage partition migration",
        "output_packet_key": "command_center_3_storage_partition_migration_execution_packet",
        "button_gated": True,
        "current_backend": "local_partition_writer_pipeline",
        "external_call_policy": "confirm_gated_local_partition_write_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "partition_policy": "explicit_scope_bound_partition_write_source_preserved",
        "requires_confirm_partition_migration": True,
        "requires_dry_run_scope_hash": True,
        "writes_parquet_on_post": True,
        "writes_only_ignored_local_parquet": True,
        "reads_row_payloads": True,
        "deletes_source_files": False,
        "refreshes_external_sources_on_post": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_compaction_dry_run",
        "route": "POST /api/storage/compaction/dry-run",
        "label": "生成 Storage compaction dry-run",
        "output_packet_key": "command_center_3_storage_compaction_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_compaction_plan_only_no_external_call",
        "possible_external_sources": [],
        "compaction_policy": "dry_run_only_no_parquet_rewrite",
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "physical_compaction_executed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_compaction_execution",
        "route": "POST /api/storage/compaction/execute",
        "label": "执行 Storage compaction",
        "output_packet_key": "command_center_3_storage_compaction_execution_packet",
        "button_gated": True,
        "current_backend": "local_partitioned_parquet_compaction_pipeline",
        "external_call_policy": "confirm_gated_local_compaction_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "compaction_policy": "scope_bound_staging_backup_readback",
        "requires_confirm_compaction": True,
        "requires_dry_run_scope_hash": True,
        "writes_parquet_on_post": True,
        "writes_only_ignored_local_parquet": True,
        "reads_row_payloads": True,
        "deletes_artifacts": False,
        "refreshes_external_sources_on_post": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_cache_ttl_dry_run",
        "route": "POST /api/storage/cache-ttl/dry-run",
        "label": "生成 Storage cache TTL dry-run",
        "output_packet_key": "command_center_3_storage_cache_ttl_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_ttl_plan_only_no_external_call",
        "possible_external_sources": [],
        "ttl_policy": "dry_run_only_no_refresh_no_external_call",
        "cache_get_external_calls": False,
        "refreshes_external_sources_on_post": False,
        "writes_parquet_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "refresh_executed": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_duckdb_read_validation",
        "route": "POST /api/storage/duckdb-read/validate",
        "label": "验证 Storage DuckDB 本地只读查询合同",
        "output_packet_key": "command_center_3_storage_duckdb_read_validation_packet",
        "button_gated": True,
        "current_backend": "local_duckdb_read_validation_pipeline",
        "external_call_policy": "local_duckdb_read_validation_no_write_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "read_validation_only": True,
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "query_result_contract_schema_version": "duckdb_query_result_contract.v1",
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": False,
        "deletes_artifacts_on_post": False,
        "refreshes_external_sources_on_post": False,
        "reads_env_files": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_physical_execution_request",
        "route": "POST /api/storage/physical-execution-request",
        "label": "生成 Storage physical execution request ticket",
        "output_packet_key": "command_center_3_storage_physical_execution_request_packet",
        "button_gated": True,
        "current_backend": "local_physical_execution_request_pipeline",
        "external_call_policy": "local_storage_physical_execution_request_no_write_no_delete_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05/LTG-11",
        "local_execution_request_only": True,
        "requires_user_confirmation": True,
        "requires_bound_scope_hash": True,
        "target_storage_task_route": "POST /api/storage/physical-execution/phase-a",
        "target_storage_task_type": "run_storage_physical_execution_phase_a",
        "creates_physical_task": False,
        "physical_task_executed_by_request": False,
        "physical_execution_implemented": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": False,
        "deletes_artifacts_on_post": False,
        "refreshes_external_sources_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_physical_execution_phase_a",
        "route": "POST /api/storage/physical-execution/phase-a",
        "label": "执行 Storage physical execution Phase A 本地证据整合",
        "output_packet_key": "command_center_3_storage_physical_execution_phase_a_packet",
        "button_gated": True,
        "current_backend": "local_physical_execution_phase_a_evidence_pipeline",
        "external_call_policy": "local_storage_physical_execution_phase_a_no_write_no_delete_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "local_phase_a_execution_only": True,
        "requires_user_confirmation": True,
        "requires_bound_scope_hash": True,
        "requires_physical_execution_request": True,
        "requires_durable_evidence_recipe": True,
        "creates_physical_task": True,
        "physical_task_executed_by_request": False,
        "physical_execution_implemented": True,
        "physical_execution_complete": False,
        "phase_a_local_evidence_done": True,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": False,
        "deletes_artifacts_on_post": False,
        "refreshes_external_sources_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_current_result_atomic_promotion",
        "route": "POST /api/storage/current-result/atomic-promote",
        "label": "原子晋级当前搜票结果到本地版本化 Parquet",
        "output_packet_key": "command_center_3_storage_current_result_atomic_promotion_packet",
        "button_gated": True,
        "current_backend": "local_versioned_parquet_atomic_pointer_pipeline",
        "external_call_policy": "local_storage_write_no_provider_model_or_trade",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "requires_user_confirmation": True,
        "requires_canonical_result_lineage": True,
        "requires_expected_symbol_and_result_version": True,
        "writes_parquet_on_post": True,
        "writes_manifest_on_post": True,
        "manifest_scope": "dataset_local_immutable_version_inventory",
        "writes_atomic_current_pointer_on_post": True,
        "preserves_last_good_pointer": True,
        "refreshes_external_sources_on_post": False,
        "deletes_artifacts_on_post": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_current_result_retention_cleanup",
        "route": "POST /api/storage/current-result/retention-cleanup",
        "label": "清理已绑定计划中的旧投研结果版本",
        "output_packet_key": "command_center_3_storage_current_result_retention_cleanup_packet",
        "button_gated": True,
        "current_backend": "local_versioned_parquet_retention_cleanup_pipeline",
        "external_call_policy": "local_storage_delete_bound_plan_no_provider_model_or_trade",
        "possible_external_sources": [],
        "ltg": "LTG-05",
        "requires_user_confirmation": True,
        "requires_current_plan_hash": True,
        "requires_exact_candidate_version_ids": True,
        "protects_current_pointer": True,
        "protects_last_good_pointer": True,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": True,
        "deletes_artifacts_on_post": True,
        "refreshes_external_sources_on_post": False,
        "production_storage_complete": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_storage_production_promotion_review",
        "route": "POST /api/storage/production-promotion-review",
        "label": "记录 Storage production promotion review",
        "output_packet_key": "command_center_3_storage_production_promotion_review_packet",
        "button_gated": True,
        "current_backend": "local_storage_production_promotion_review_pipeline",
        "external_call_policy": "local_storage_production_promotion_review_no_write_no_delete_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-05/LTG-11",
        "local_promotion_review_only": True,
        "requires_user_confirmation": True,
        "requires_bound_scope_hash": True,
        "requires_physical_execution_request": True,
        "marks_durable_review_visible": True,
        "ready_to_mark_production_storage_complete": False,
        "production_storage_complete": False,
        "creates_physical_task": False,
        "physical_task_executed_by_review": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "cache_get_external_calls": False,
        "writes_parquet_on_post": False,
        "writes_manifest_on_post": False,
        "deletes_artifacts_on_post": False,
        "refreshes_external_sources_on_post": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_synthetic_healthcheck",
        "route": "POST /api/worker/synthetic-healthcheck",
        "label": "运行 Worker synthetic healthcheck",
        "output_packet_key": "command_center_3_worker_synthetic_healthcheck_packet",
        "button_gated": True,
        "current_backend": "local_synthetic_healthcheck_pipeline",
        "external_call_policy": "explicit_post_local_synthetic_worker_healthcheck_no_process_start",
        "possible_external_sources": [],
        "synthetic_task_only": True,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "production_worker_complete": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_activation_review",
        "route": "POST /api/worker/activation-review",
        "label": "审查 Worker activation 本地证据",
        "output_packet_key": "command_center_3_worker_activation_review_packet",
        "button_gated": True,
        "current_backend": "local_activation_review_pipeline",
        "external_call_policy": "explicit_post_local_worker_activation_review_no_process_start",
        "possible_external_sources": [],
        "local_review_only": True,
        "requires_synthetic_healthcheck": True,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_production_evidence_plan",
        "route": "POST /api/worker/production-evidence-plan",
        "label": "生成 Worker production evidence plan",
        "output_packet_key": "command_center_3_worker_production_evidence_plan_packet",
        "button_gated": True,
        "current_backend": "local_production_evidence_plan_pipeline",
        "external_call_policy": "explicit_post_local_worker_production_evidence_plan_no_process_start",
        "possible_external_sources": [],
        "local_plan_only": True,
        "requires_activation_review": True,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "writes_worker_logs": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_runtime_qa_execution_request",
        "route": "POST /api/worker/runtime-qa-execution-request",
        "label": "生成 Worker runtime QA execution request ticket",
        "output_packet_key": "command_center_3_worker_runtime_qa_execution_request_packet",
        "button_gated": True,
        "current_backend": "local_runtime_qa_execution_request_pipeline",
        "external_call_policy": "explicit_post_local_worker_runtime_qa_execution_request_no_process_start",
        "possible_external_sources": [],
        "ltg": "LTG-06/LTG-11",
        "local_execution_request_only": True,
        "requires_operator_approval": True,
        "requires_production_evidence_plan": True,
        "requires_bound_scope_hash": True,
        "target_worker_task_route": "future POST /api/worker/runtime-qa-execution",
        "target_worker_task_type": "run_worker_runtime_qa_execution",
        "creates_runtime_qa_task": False,
        "runtime_qa_task_executed_by_request": False,
        "runtime_qa_execution_implemented": False,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "writes_worker_logs": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_runtime_qa_dry_run",
        "route": "POST /api/worker/runtime-qa-dry-run",
        "label": "生成 Worker runtime QA dry-run receipt",
        "output_packet_key": "command_center_3_worker_runtime_qa_dry_run_packet",
        "button_gated": True,
        "current_backend": "local_runtime_qa_dry_run_pipeline",
        "external_call_policy": "explicit_post_local_worker_runtime_qa_dry_run_no_process_start_no_dispatch",
        "possible_external_sources": [],
        "ltg": "LTG-06/LTG-11",
        "local_dry_run_only": True,
        "requires_operator_approval": True,
        "requires_runtime_qa_execution_request": True,
        "requires_bound_scope_hash": True,
        "target_worker_task_route": "future POST /api/worker/runtime-qa-execution",
        "target_worker_task_type": "run_worker_runtime_qa_execution",
        "creates_runtime_qa_task": False,
        "runtime_qa_task_executed_by_dry_run": False,
        "runtime_qa_execution_implemented": False,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "writes_worker_logs": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_runtime_qa_execution",
        "route": "POST /api/worker/runtime-qa-execution",
        "label": "执行 Worker runtime QA local fallback evidence",
        "output_packet_key": "command_center_3_worker_runtime_qa_execution_packet",
        "button_gated": True,
        "current_backend": "local_runtime_qa_execution_pipeline",
        "external_call_policy": "explicit_post_local_worker_runtime_qa_execution_no_process_start_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-06/LTG-11",
        "local_runtime_qa_execution_only": True,
        "requires_operator_approval": True,
        "requires_runtime_qa_dry_run": True,
        "requires_bound_scope_hash": True,
        "creates_runtime_qa_task": True,
        "runtime_qa_task_executed_by_execution": True,
        "runtime_qa_execution_implemented": True,
        "proves_local_fallback_round_trip": True,
        "proves_append_only_worker_log_event": True,
        "proves_celery_process": False,
        "proves_redis_broker": False,
        "proves_cross_process_controls": False,
        "cache_get_external_calls": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_cross_process_controls": False,
        "writes_worker_logs": True,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_worker_production_promotion_review",
        "route": "POST /api/worker/production-promotion-review",
        "label": "审查 Worker production promotion 本地证据",
        "output_packet_key": "command_center_3_worker_production_promotion_review_packet",
        "button_gated": True,
        "current_backend": "local_worker_production_promotion_review_pipeline",
        "external_call_policy": "explicit_post_local_worker_promotion_review_no_process_start_no_external_call",
        "possible_external_sources": [],
        "ltg": "LTG-06/LTG-11",
        "local_review_only": True,
        "requires_operator_approval": True,
        "requires_runtime_qa_execution": True,
        "requires_durable_evidence_recipe": True,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "validates_celery_process": False,
        "validates_redis_broker": False,
        "validates_live_queue_round_trip": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_qmt_readonly_local_replay",
        "route": "POST /api/qmt-replay/local-simulate",
        "label": "运行 QMT 脱敏导出本地确定性回放",
        "output_packet_key": "command_center_3_qmt_replay_current",
        "button_gated": True,
        "current_backend": "local_qmt_readonly_decimal_replay_pipeline",
        "external_call_policy": "caller_supplied_export_or_bound_lineage_only_no_qmt_connection",
        "possible_external_sources": [],
        "future_external_sources": ["qmt"],
        "ltg": "LTG-12",
        "requires_user_approval": True,
        "requires_local_research_replay_mode": True,
        "requires_bound_source_scope_hash": True,
        "allowed_scenarios": ["baseline", "stress", "recovery"],
        "allowed_max_frames": [12, 24, 48],
        "caller_supplied_sanitized_export_supported": True,
        "deterministic_decimal_replay": True,
        "virtual_fill_only": True,
        "qmt_connector_implemented": False,
        "qmt_process_discovery_implemented": False,
        "broker_session_implemented": False,
        "account_query_implemented": False,
        "real_order_path_implemented": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
    },
    {
        "task_type": "run_chokepoint_scan",
        "route": "POST /api/chokepoint/run",
        "label": "运行产业链瓶颈扫描",
        "output_packet_key": "command_center_chokepoint_scan_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_deepseek_capable",
        "possible_external_sources": ["deepseek"],
        "deepseek_model_strategy_purpose": "explain",
        "deepseek_model_config_keys": list(DEEPSEEK_MODEL_CONFIG_KEYS["explain"]),
        "deepseek_model_source": "config.get_deepseek_model('explain')",
        "does_not_hardcode_deepseek_model": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "probe_serenity_github",
        "route": "POST /api/serenity/github-probe",
        "label": "校验 Serenity GitHub 当前状态",
        "output_packet_key": "command_center_serenity_method_radar_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_github_probe_capable",
        "possible_external_sources": ["github"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
]

TASK_LIFECYCLE_POST_ROUTES = [
    {
        "route": "POST /api/tasks/{task_id}/cancel",
        "label": "取消本地任务",
        "route_type": "local_lifecycle",
        "button_gated": True,
        "current_backend": "local_status_update_only",
        "external_call_policy": "local_cancel_no_external_call",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "route": "POST /api/tasks/{task_id}/retry",
        "label": "手动重试本地任务",
        "route_type": "local_lifecycle",
        "button_gated": True,
        "current_backend": "local_retry_record_only",
        "external_call_policy": "local_retry_no_external_call",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
]

TASK_CONTROL_PLANE_POST_ROUTES = [
    {
        "route": "POST /api/audit/external-production-attestation",
        "label": "导入外部签名证明到本地完整性注册表",
        "route_type": "local_external_attestation_control_plane",
        "button_gated": True,
        "current_backend": "local_ed25519_verification_registry",
        "external_call_policy": "signed_envelope_local_verification_only_no_external_call",
        "possible_external_sources": [],
        "creates_task": False,
        "production_eligible": False,
        "structural_production_blockers": [
            "external_monotonic_anchor_unavailable",
            "trusted_head_key_epoch_unavailable",
            "production_consumer_not_wired",
        ],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "route": "POST /api/audit/production-release-promotion",
        "label": "确认并写入 current-head 生产发布提升事件",
        "route_type": "local_release_control_plane",
        "button_gated": True,
        "current_backend": "local_hmac_append_only_release_promotion_journal",
        "external_call_policy": "explicit_literal_approval_local_write_no_external_call",
        "possible_external_sources": [],
        "requires_user_confirmation": True,
        "creates_task": False,
        "authoritative_state": "hmac_append_only_release_promotion_journal",
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "route": "POST /api/next-session/production-replacement",
        "label": "确认并审查次日图谱 current-head 生产替代证据",
        "route_type": "local_production_replacement_control_plane",
        "button_gated": True,
        "current_backend": "local_fail_closed_next_session_replacement_journal",
        "external_call_policy": "explicit_post_local_qa_review_only_no_external_call",
        "possible_external_sources": [],
        "requires_user_confirmation": True,
        "creates_task": False,
        "production_eligible": False,
        "structural_production_blockers": [
            "external_trusted_approval_capability_unavailable",
            "rollback_resistant_high_water_unavailable",
        ],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "route": "POST /api/storage/cache-ttl/production-attestation",
        "label": "导入 Storage TTL 外部签名证明到本地完整性注册表",
        "route_type": "local_external_attestation_control_plane",
        "button_gated": True,
        "current_backend": "local_ed25519_verification_registry",
        "external_call_policy": "signed_envelope_local_verification_only_no_external_call",
        "possible_external_sources": [],
        "creates_task": False,
        "production_eligible": False,
        "structural_production_blockers": [
            "external_monotonic_anchor_unavailable",
            "trusted_head_key_epoch_unavailable",
            "production_consumer_not_wired",
        ],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
]

TASK_RETRY_POLICY_VERSION = "task_retry_policy.audit.v1"
TASK_RETRY_POLICY_DEFAULT = {
    "manual_retry_allowed": True,
    "max_attempts": 2,
    "backoff": "manual_linear_15s_60s",
}
TASK_RETRY_POLICY_BY_TYPE: dict[str, dict[str, Any]] = {
    "refresh_tushare_facts": {
        "manual_retry_allowed": True,
        "max_attempts": 3,
        "backoff": "manual_exponential_30s_120s_300s",
    },
    "refresh_factor_data": {
        "manual_retry_allowed": True,
        "max_attempts": 3,
        "backoff": "manual_exponential_30s_120s_300s",
    },
    "run_factor_light": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_factor_universe_research_plan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_deepseek_factor_explanation": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_deepseek_provider_benchmark_scope_ticket": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_deepseek_provider_benchmark_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_deepseek_provider_benchmark": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "build_next_session_projection": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_next_session_browser_qa_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_package_artifact_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_packaged_runtime_launch_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_backend_offline_packaged_ux_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_backend_startup_runtime_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_config_log_runtime_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_tauri_signing_notarization_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_streamlit_ordinary_workflow_parity_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_next_session_streamlit_parity_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_packet_change",
    },
    "run_next_session_production_promotion_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_promotion_evidence_change",
    },
    "run_candidate_radar_quick_scan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_quant_projection": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_full_pool_plan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_full_pool_local_scan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_full_pool_worker_fallback": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_deep_scan_worker_fallback": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_deep_scan_plan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_deep_scan_local_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_browser_qa_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_candidate_radar_production_replacement_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_production_promotion_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_production_promotion_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_legacy_retirement_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_worker_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_provider_parity_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_provider_parity_acceptance": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_candidate_radar_quant_projection_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_motion_browser_qa_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_motion_production_promotion_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_motion_visual_performance_promotion_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_scope_change",
    },
    "run_storage_artifact_cleanup_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_schema_validation_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_backtest_results_schema_seed": {
        "manual_retry_allowed": True,
        "max_attempts": 1,
        "backoff": "manual_review_before_retry",
    },
    "run_storage_schema_validation_acceptance": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_schema_migration_execution": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_schema_and_manifest_validation",
    },
    "run_storage_dataset_version_manifest_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_dataset_version_manifest_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_dry_run",
    },
    "run_storage_dataset_version_manifest_write": {
        "manual_retry_allowed": True,
        "max_attempts": 1,
        "backoff": "manual_review_before_retry",
    },
    "run_storage_dataset_version_manifest_validate": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_validate_after_write",
    },
    "run_storage_partition_migration_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_partition_migration_execution": {
        "manual_retry_allowed": True,
        "max_attempts": 1,
        "backoff": "manual_review_after_scope_or_target_change",
    },
    "run_storage_compaction_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_compaction_execution": {
        "manual_retry_allowed": True,
        "max_attempts": 1,
        "backoff": "manual_review_after_scope_or_target_change",
    },
    "run_storage_cache_ttl_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_duckdb_read_validation": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_physical_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_recipe_change",
    },
    "run_storage_physical_execution_phase_a": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_phase_a_scope_change",
    },
    "run_storage_current_result_atomic_promotion": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_retry_after_canonical_lineage_change",
    },
    "run_storage_current_result_retention_cleanup": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_retry_after_retention_plan_recheck",
    },
    "run_storage_production_promotion_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_physical_execution_request_change",
    },
    "run_worker_synthetic_healthcheck": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_worker_activation_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_worker_production_evidence_plan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_worker_runtime_qa_execution_request": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_recipe_change",
    },
    "run_worker_runtime_qa_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_request_or_recipe_change",
    },
    "run_worker_runtime_qa_execution": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_dry_run_or_scope_change",
    },
    "run_worker_production_promotion_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_review_after_runtime_evidence_change",
    },
    "run_chokepoint_scan": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "probe_serenity_github": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
}
TASK_RETRYABLE_STATUSES = ["failed"]
TASK_LOCK_POLICY_VERSION = "task_lock_policy.local_dispatch.v1"
TASK_DEDUPE_POLICY_VERSION = "task_dedupe_policy.audit.v1"
TASK_TERMINAL_STATUSES = {"success", "failed", "cancelled"}
TASK_LOCK_ENFORCED = True
TASK_DISPATCH_DEDUPE_ENFORCED = True


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="microseconds")


def _build_route_coverage() -> dict[str, Any]:
    task_routes = [str(item.get("route") or "") for item in TASK_CATALOG]
    lifecycle_routes = [str(item.get("route") or "") for item in TASK_LIFECYCLE_POST_ROUTES]
    control_plane_routes = [str(item.get("route") or "") for item in TASK_CONTROL_PLANE_POST_ROUTES]
    known_post_routes = task_routes + lifecycle_routes + control_plane_routes
    route_contracts = TASK_CATALOG + TASK_LIFECYCLE_POST_ROUTES + TASK_CONTROL_PLANE_POST_ROUTES
    return {
        "status": "ready",
        "scope": "command_center_3_button_gated_post_routes",
        "task_creation_route_count": len(task_routes),
        "local_lifecycle_route_count": len(lifecycle_routes),
        "local_control_plane_route_count": len(control_plane_routes),
        "known_post_route_count": len(known_post_routes),
        "task_creation_routes": task_routes,
        "local_lifecycle_routes": lifecycle_routes,
        "local_control_plane_routes": control_plane_routes,
        "known_post_routes": known_post_routes,
        "uncovered_post_routes": [],
        "all_known_post_routes_button_gated": all(bool(item.get("button_gated")) for item in route_contracts),
        "call_ledger_required_for_all_known_post_routes": all(
            bool(item.get("call_ledger_required")) for item in route_contracts
        ),
        "cache_reads_create_no_tasks": True,
        "cancel_routes_external_calls": False,
        "retry_routes_external_calls": False,
        "lifecycle_routes_external_calls": False,
        "control_plane_routes_external_calls": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _build_implementation_status() -> dict[str, Any]:
    backend_counts: dict[str, int] = {}
    stub_task_types: list[str] = []
    local_pipeline_task_types: list[str] = []
    guarded_local_task_types: list[str] = []
    external_capable_task_types: list[str] = []

    for item in TASK_CATALOG:
        task_type = str(item.get("task_type") or "")
        backend = str(item.get("current_backend") or "unknown")
        backend_counts[backend] = backend_counts.get(backend, 0) + 1
        if "stub" in backend:
            stub_task_types.append(task_type)
        if "pipeline" in backend or backend == "local_producer_cache_refresh_sqlite_packet_writer":
            local_pipeline_task_types.append(task_type)
        if "guarded" in backend or "sanitizer" in backend:
            guarded_local_task_types.append(task_type)
        if item.get("possible_external_sources"):
            external_capable_task_types.append(task_type)

    implemented_local_task_types = sorted(set(local_pipeline_task_types + guarded_local_task_types))
    return {
        "status": "partial_migration",
        "scope": "command_center_3_task_backend_implementation",
        "task_count": len(TASK_CATALOG),
        "backend_counts": backend_counts,
        "stub_task_count": len(stub_task_types),
        "local_pipeline_task_count": len(local_pipeline_task_types),
        "guarded_local_task_count": len(guarded_local_task_types),
        "implemented_local_task_count": len(implemented_local_task_types),
        "external_capable_task_count": len(external_capable_task_types),
        "stub_task_types": stub_task_types,
        "local_pipeline_task_types": local_pipeline_task_types,
        "guarded_local_task_types": guarded_local_task_types,
        "implemented_local_task_types": implemented_local_task_types,
        "external_capable_task_types": external_capable_task_types,
        "all_external_capable_tasks_are_button_gated": all(
            bool(item.get("button_gated"))
            for item in TASK_CATALOG
            if item.get("possible_external_sources")
        ),
        "all_external_capable_tasks_require_call_ledger": all(
            bool(item.get("call_ledger_required"))
            for item in TASK_CATALOG
            if item.get("possible_external_sources")
        ),
        "note": "任务目录展示实现状态，避免把 stub/guarded/local pipeline 误读为完整生产迁移。",
    }


def _retry_policy_for_task(
    task_type: str,
    *,
    status: str = "pending",
    attempt_number: int | None = None,
) -> dict[str, Any]:
    base = dict(TASK_RETRY_POLICY_DEFAULT)
    base.update(TASK_RETRY_POLICY_BY_TYPE.get(str(task_type or ""), {}))
    max_attempts = max(1, int(base.get("max_attempts") or 1))
    attempt = max(1, int(attempt_number or 1))
    attempts_remaining = max(0, max_attempts - attempt)
    manual_retry_allowed = bool(base.get("manual_retry_allowed"))
    manual_retry_eligible = bool(status in TASK_RETRYABLE_STATUSES and manual_retry_allowed and attempts_remaining > 0)
    return {
        "policy_version": TASK_RETRY_POLICY_VERSION,
        "enabled": False,
        "auto_retry_enabled": False,
        "manual_retry_allowed": manual_retry_allowed,
        "manual_retry_eligible": manual_retry_eligible,
        "requires_new_task_id": True,
        "max_attempts": max_attempts,
        "attempt_number": attempt,
        "attempts_remaining": attempts_remaining,
        "backoff": str(base.get("backoff") or "manual_only_no_auto_backoff"),
        "retryable_statuses": list(TASK_RETRYABLE_STATUSES),
        "retry_scope": "manual_operator_triggered_new_task",
        "cache_api_can_retry": False,
        "auto_retry_on_get": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "审计元数据只说明失败后可人工重建任务；当前不会自动重试、不会自动外联。",
    }


def _active_lock_conflicts(lock_key: str, *, exclude_task_id: str = "") -> list[str]:
    seen: set[str] = set()
    conflicts: list[str] = []
    candidates = list(_TASKS.values()) + _list_persisted_tasks()
    for task in candidates:
        task_id = str(task.get("task_id") or "")
        if not task_id or task_id == str(exclude_task_id or "") or task_id in seen:
            continue
        seen.add(task_id)
        if str(task.get("lock_key") or "") != str(lock_key or ""):
            continue
        if str(task.get("status") or "pending") in TASK_TERMINAL_STATUSES:
            continue
        conflicts.append(task_id)
    return sorted(conflicts)


def _idempotency_duplicates(idempotency_key: str, *, exclude_task_id: str = "") -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    active: list[str] = []
    historical: list[str] = []
    candidates = list(_TASKS.values()) + _list_persisted_tasks()
    for task in candidates:
        task_id = str(task.get("task_id") or "")
        if not task_id or task_id == str(exclude_task_id or "") or task_id in seen:
            continue
        seen.add(task_id)
        if str(task.get("idempotency_key") or "") != str(idempotency_key or ""):
            continue
        if str(task.get("status") or "pending") in TASK_TERMINAL_STATUSES:
            historical.append(task_id)
        else:
            active.append(task_id)
    return sorted(active), sorted(historical)


def _dedupe_policy_for_task(
    task_type: str,
    *,
    task_id: str,
    input_hash: str,
    idempotency_key: str,
) -> dict[str, Any]:
    active_duplicates, historical_duplicates = _idempotency_duplicates(idempotency_key, exclude_task_id=task_id)
    duplicate_detected = bool(active_duplicates or historical_duplicates)
    return {
        "policy_version": TASK_DEDUPE_POLICY_VERSION,
        "dedupe_scope": "task_type_payload",
        "idempotency_key": idempotency_key,
        "task_type": str(task_type or ""),
        "input_hash": str(input_hash or ""),
        "duplicate_detection_enabled": True,
        "duplicate_detected": duplicate_detected,
        "active_duplicate_count": len(active_duplicates),
        "historical_duplicate_count": len(historical_duplicates),
        "active_duplicate_task_ids": active_duplicates[:5],
        "historical_duplicate_task_ids": historical_duplicates[:5],
        "dispatch_dedupe_enabled": TASK_DISPATCH_DEDUPE_ENFORCED,
        "dispatch_dedupe_enforced": False,
        "audit_only": not TASK_DISPATCH_DEDUPE_ENFORCED,
        "cache_api_can_dedupe": False,
        "auto_blocks_task_creation": TASK_DISPATCH_DEDUPE_ENFORCED,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "本地 dispatch 去重会复用同 task_type+payload 的非终态任务；不会自动外联。",
    }


def _lock_policy_for_task(
    task_type: str,
    *,
    task_id: str,
    input_hash: str,
    lock_key: str,
    status: str = "pending",
) -> dict[str, Any]:
    active_conflicts = _active_lock_conflicts(lock_key, exclude_task_id=task_id)
    lock_active = status not in TASK_TERMINAL_STATUSES
    return {
        "policy_version": TASK_LOCK_POLICY_VERSION,
        "lock_scope": "task_type_payload",
        "lock_key": lock_key,
        "lock_key_source": "task_type_plus_input_hash",
        "task_type": str(task_type or ""),
        "input_hash": str(input_hash or ""),
        "lock_active": lock_active,
        "lock_enforced": False,
        "lock_enforcement_enabled": TASK_LOCK_ENFORCED,
        "audit_only": not TASK_LOCK_ENFORCED,
        "conflict_detection_enabled": True,
        "lock_conflict_detected": bool(lock_active and active_conflicts),
        "active_conflict_count": len(active_conflicts) if lock_active else 0,
        "active_conflict_task_ids": active_conflicts[:5] if lock_active else [],
        "cache_api_can_acquire_lock": False,
        "auto_blocks_task_creation": TASK_LOCK_ENFORCED,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "本地 dispatch 锁会复用同 task_type+payload 的非终态任务；不会自动外联。",
    }


def _build_retry_policy_summary() -> dict[str, Any]:
    task_policies = {
        str(item.get("task_type") or ""): _retry_policy_for_task(str(item.get("task_type") or ""))
        for item in TASK_CATALOG
    }
    return {
        "policy_version": TASK_RETRY_POLICY_VERSION,
        "status": "audit_ready",
        "auto_retry_enabled": False,
        "manual_retry_supported": True,
        "manual_retry_requires_new_task_id": True,
        "cache_api_can_retry": False,
        "retryable_statuses": list(TASK_RETRYABLE_STATUSES),
        "task_policies": task_policies,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _catalog_task_item(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    row["retry_policy"] = _retry_policy_for_task(str(row.get("task_type") or ""))
    row["lock_policy"] = {
        "policy_version": TASK_LOCK_POLICY_VERSION,
        "lock_scope": "task_type_payload",
        "lock_enforced": False,
        "lock_enforcement_enabled": TASK_LOCK_ENFORCED,
        "audit_only": not TASK_LOCK_ENFORCED,
        "conflict_detection_enabled": True,
        "cache_api_can_acquire_lock": False,
        "auto_blocks_task_creation": TASK_LOCK_ENFORCED,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    row["dedupe_policy"] = {
        "policy_version": TASK_DEDUPE_POLICY_VERSION,
        "dedupe_scope": "task_type_payload",
        "duplicate_detection_enabled": True,
        "dispatch_dedupe_enabled": TASK_DISPATCH_DEDUPE_ENFORCED,
        "dispatch_dedupe_enforced": False,
        "audit_only": not TASK_DISPATCH_DEDUPE_ENFORCED,
        "cache_api_can_dedupe": False,
        "auto_blocks_task_creation": TASK_DISPATCH_DEDUPE_ENFORCED,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    purpose = row.get("deepseek_model_strategy_purpose")
    if purpose:
        strategy = build_deepseek_model_strategy_ref(str(purpose))
        strategy["model_source"] = str(row.get("deepseek_model_source") or strategy.get("model_source"))
        strategy["does_not_hardcode_model"] = bool(row.get("does_not_hardcode_deepseek_model"))
        row["deepseek_model_strategy"] = strategy
    return row


def build_task_catalog() -> dict[str, Any]:
    route_coverage = _build_route_coverage()
    implementation_status = _build_implementation_status()
    retry_policy_summary = _build_retry_policy_summary()
    return {
        "packet_key": "command_center_3_task_catalog",
        "schema_version": "command_center_3_task_catalog.v1",
        "status": "ready",
        "tasks": [_catalog_task_item(item) for item in TASK_CATALOG],
        "task_lifecycle_routes": [dict(item) for item in TASK_LIFECYCLE_POST_ROUTES],
        "control_plane_post_routes": [dict(item) for item in TASK_CONTROL_PLANE_POST_ROUTES],
        "route_coverage": route_coverage,
        "implementation_status": implementation_status,
        "retry_policy_summary": retry_policy_summary,
        "task_count": len(TASK_CATALOG),
        "policy": {
            "get_catalog_cache_only": True,
            "all_tasks_button_gated": all(bool(item.get("button_gated")) for item in TASK_CATALOG),
            "all_known_post_routes_button_gated": bool(route_coverage["all_known_post_routes_button_gated"]),
            "call_ledger_required_for_all": all(bool(item.get("call_ledger_required")) for item in TASK_CATALOG),
            "call_ledger_required_for_all_known_post_routes": bool(route_coverage["call_ledger_required_for_all_known_post_routes"]),
            "implementation_status_is_read_only": True,
            "stub_tasks_must_not_be_reported_as_complete": True,
            "supports_local_task_cancel": True,
            "retry_policy_audit_ready": True,
            "automatic_retry_enabled": False,
            "manual_retry_requires_post_task": True,
            "cancel_task_external_calls": False,
            "retry_task_external_calls": False,
            "cancel_route_in_lifecycle_catalog": True,
            "retry_route_in_lifecycle_catalog": True,
            "post_task_may_trigger_external_request": True,
            "cache_api_external_calls": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        },
        "external_sources": sorted({source for item in TASK_CATALOG for source in item.get("possible_external_sources", [])}),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "call_ledger": [
            {
                "api": "local_task_catalog_cache",
                "request_params_safe": {},
                "row_count": len(TASK_CATALOG),
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "GET /api/tasks/catalog 只读取本地任务目录；不会调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。"
        ],
    }


def _is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SECRET_KEYWORDS)


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(key: Any, value: Any) -> Any:
    if _is_secret_key(key):
        return None
    if isinstance(value, dict):
        return {str(child_key): safe for child_key, child_value in value.items() if (safe := _safe_value(child_key, child_value)) is not None}
    if isinstance(value, list):
        return [_safe_value(key, item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_payload(payload: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {str(key): safe for key, value in payload.items() if (safe := _safe_value(key, value)) is not None}


def _task_input_hash(task_type: str, payload_safe: dict[str, Any]) -> str:
    payload = {
        "task_type": str(task_type or ""),
        "payload_safe": payload_safe,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _status_event(status: str, *, progress: float, current_step: str, at: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "progress": float(progress),
        "current_step": current_step,
        "at": at or _now_iso(),
    }


def _task_log_event(
    event: str,
    *,
    status: str,
    current_step: str,
    message: str = "",
    at: str | None = None,
) -> dict[str, Any]:
    return {
        "event": _safe_text(event, limit=80),
        "status": status if status in TASK_STATUSES else "unknown",
        "current_step": _safe_text(current_step, limit=160),
        "message_safe": _safe_text(message, limit=240),
        "at": at or _now_iso(),
        "external": False,
        "external_calls_triggered": False,
        "contains_secret": False,
        "stack_trace_included": False,
    }


def _persist_task(task: dict[str, Any]) -> dict[str, Any]:
    _TASKS[str(task["task_id"])] = task
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_task_status(task)
    except Exception:
        task.setdefault("warnings", []).append("task_metadata_sqlite_write_failed_safe")
    return task


def _read_persisted_task(task_id: str) -> dict[str, Any] | None:
    if not SQLITE_META_PATH.exists():
        return None
    try:
        task = SQLiteMetaStore(SQLITE_META_PATH, read_only=True).read_task_status(str(task_id))
    except Exception:
        return None
    return task if isinstance(task, dict) else None


def _list_persisted_tasks() -> list[dict[str, Any]]:
    if not SQLITE_META_PATH.exists():
        return []
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH, read_only=True)
        tasks = [task for item in store.list_task_metadata() if (task := store.read_task_status(str(item.get("task_id") or "")))]
    except Exception:
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _task_catalog_entry(task_type: str) -> dict[str, Any]:
    for item in TASK_CATALOG:
        if item.get("task_type") == task_type:
            return dict(item)
    return {}


def _stub_request_params_safe(task_type: str) -> dict[str, Any]:
    entry = _task_catalog_entry(task_type)
    purpose = entry.get("deepseek_model_strategy_purpose")
    if not purpose:
        return {}
    strategy = build_deepseek_model_strategy_ref(str(purpose))
    strategy["model_source"] = str(entry.get("deepseek_model_source") or strategy.get("model_source"))
    strategy["does_not_hardcode_model"] = bool(entry.get("does_not_hardcode_deepseek_model"))
    return {
        "deepseek_model_strategy": strategy
    }


def _stub_call_ledger(task_type: str, now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": task_type,
            "request_params_safe": _stub_request_params_safe(task_type),
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "stub_not_called",
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _cancel_call_ledger(task_id: str, now: str, *, reason_safe: str = "") -> dict[str, Any]:
    return {
        "api": "local_task_cancel",
        "task_id": str(task_id),
        "request_params_safe": {"reason": reason_safe} if reason_safe else {},
        "row_count": 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": "cancelled_locally_no_external_call",
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _retry_call_ledger(
    task_id: str,
    now: str,
    *,
    new_task_id: str = "",
    call_status: str = "manual_retry_created_no_external_call",
    reason_safe: str = "",
) -> dict[str, Any]:
    return {
        "api": "local_task_retry",
        "request_params_safe": {
            "source_task_id": _safe_text(task_id, limit=120),
            "new_task_id": _safe_text(new_task_id, limit=120),
            "reason": reason_safe,
        },
        "row_count": 1 if new_task_id else 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": call_status,
        "error_message_safe": "" if call_status == "manual_retry_created_no_external_call" else call_status,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _dedupe_reuse_call_ledger(existing_task_id: str, now: str, *, task_type: str, input_hash: str) -> dict[str, Any]:
    return {
        "api": "local_task_dispatch_dedupe",
        "request_params_safe": {
            "existing_task_id": _safe_text(existing_task_id, limit=120),
            "task_type": _safe_text(task_type, limit=120),
            "input_hash": _safe_text(input_hash, limit=120),
        },
        "row_count": 1,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": "reused_active_task_no_external_call",
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _lock_reuse_call_ledger(existing_task_id: str, now: str, *, task_type: str, input_hash: str) -> dict[str, Any]:
    return {
        "api": "local_task_dispatch_lock",
        "request_params_safe": {
            "existing_task_id": _safe_text(existing_task_id, limit=120),
            "task_type": _safe_text(task_type, limit=120),
            "input_hash": _safe_text(input_hash, limit=120),
        },
        "row_count": 1,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": "lock_reused_active_task_no_external_call",
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def task_not_found_call_ledger(task_id: str, *, api: str = "local_task_status_lookup") -> list[dict[str, Any]]:
    return [
        {
            "api": api,
            "request_params_safe": {"task_id": _safe_text(task_id, limit=120)},
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": _now_iso(),
            "call_status": "task_not_found_no_external_call",
            "error_message_safe": "task_not_found",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def task_log_call_ledger(task_id: str, *, row_count: int) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_task_log_lookup",
            "request_params_safe": {"task_id": _safe_text(task_id, limit=120)},
            "row_count": int(row_count),
            "data_date": None,
            "local_fetched_at": _now_iso(),
            "call_status": "cache_read",
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def task_not_found_warnings(route: str) -> list[str]:
    return [
        f"{route} 只执行本地任务状态查询；任务不存在时不调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。"
    ]


def build_task_log_packet(task_id: str) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None
    task_log = list(task.get("task_log") or [])
    status_history = list(task.get("status_history") or [])
    call_ledger = task_log_call_ledger(str(task_id), row_count=len(task_log))
    return {
        "packet_key": "command_center_3_task_log_packet",
        "schema_version": "command_center_3_task_log.v1",
        "mode": "cache_only",
        "status": "ready",
        "task_id": str(task.get("task_id") or task_id),
        "task_type": str(task.get("task_type") or ""),
        "task_status": str(task.get("status") or ""),
        "storage_source": task.get("storage_source") or "memory_or_sqlite_fallback",
        "task_log": task_log,
        "task_log_count": len(task_log),
        "status_history": status_history,
        "status_history_count": len(status_history),
        "error_message_safe": _safe_text(task.get("error_message_safe", "")),
        "policy": {
            "get_task_logs_cache_only": True,
            "does_not_create_tasks": True,
            "does_not_call_external_sources": True,
            "task_logs_safe": True,
            "task_logs_include_no_raw_payload": True,
            "contains_secret": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "call_ledger": call_ledger,
        "warnings": [
            "GET /api/tasks/{task_id}/logs 只读取本地任务日志；不会调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。"
        ],
    }


def build_task_record(
    task_type: str,
    *,
    task_id: str | None = None,
    output_packet_key: str = "",
    payload: Any = None,
    status: str = "pending",
    progress: float = 0.0,
    current_step: str = "queued",
    warnings: list[str] | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_status = status if status in TASK_STATUSES else "pending"
    now = _now_iso()
    payload_safe = _safe_payload(payload)
    input_hash = _task_input_hash(task_type, payload_safe)
    record_task_id = task_id or f"local-{uuid.uuid4().hex[:12]}"
    idempotency_key = f"{task_type}:{input_hash}"
    lock_key = f"lock:{task_type}:{input_hash}"
    record = {
        "task_id": record_task_id,
        "task_type": task_type,
        "input_hash": input_hash,
        "idempotency_key": idempotency_key,
        "dedupe_scope": "local_task_type_payload",
        "dedupe_policy": _dedupe_policy_for_task(
            task_type,
            task_id=record_task_id,
            input_hash=input_hash,
            idempotency_key=idempotency_key,
        ),
        "lock_key": lock_key,
        "lock_enforced": False,
        "lock_policy": _lock_policy_for_task(
            task_type,
            task_id=record_task_id,
            input_hash=input_hash,
            lock_key=lock_key,
            status=selected_status,
        ),
        "retry_policy": _retry_policy_for_task(task_type, status=selected_status),
        "status": selected_status,
        "created_at": now,
        "started_at": now if selected_status in {"running", "success", "failed"} else None,
        "finished_at": now if selected_status in {"success", "failed", "cancelled"} else None,
        "progress": max(0.0, min(1.0, float(progress))),
        "current_step": current_step,
        "error_message_safe": "",
        "output_packet_key": output_packet_key,
        "payload_safe": payload_safe,
        "warnings": list(warnings or []),
        "call_ledger": list(call_ledger or []),
        "backend": "local_fallback",
        "external_calls_triggered": False,
        "deepseek_called": False,
        "tushare_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "status_history": [_status_event(selected_status, progress=progress, current_step=current_step, at=now)],
        "task_log": [
            _task_log_event(
                "task_created",
                status=selected_status,
                current_step=current_step,
                message="local task record created without external work",
                at=now,
            )
        ],
    }
    return record


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except Exception:
        return left == right


def _candidate_cache_replay_packet() -> dict[str, Any] | None:
    packet = None
    if SQLITE_META_PATH.exists():
        try:
            packet = SQLiteMetaStore(SQLITE_META_PATH, read_only=True).read_packet(
                "command_center_3_candidate_radar_cache"
            )
        except Exception:
            packet = None
    if packet is not None:
        if not isinstance(packet, dict):
            return None
        if packet.get("packet_key") != "command_center_3_candidate_radar_cache":
            return None
        if packet.get("schema_version") != "candidate_radar_cache.v1":
            return None
        return packet

    try:
        from . import packet_service

        snapshot_cache_path = Path(packet_service.SNAPSHOT_CACHE_PATH)
        task_meta_is_default = _same_path(Path(SQLITE_META_PATH), DEFAULT_SQLITE_META_PATH)
        snapshot_is_isolated = not _same_path(snapshot_cache_path, DEFAULT_SNAPSHOT_CACHE_PATH)
        if task_meta_is_default or snapshot_is_isolated:
            snapshot = packet_service.load_snapshot_cache()
            packet = snapshot.get("command_center_3_candidate_radar_cache") if isinstance(snapshot, dict) else None
            if (
                isinstance(packet, dict)
                and packet.get("packet_key") == "command_center_3_candidate_radar_cache"
                and packet.get("schema_version") == "candidate_radar_cache.v1"
            ):
                return packet
    except Exception:
        pass
    return None


def _candidate_cache_replay_task(task_id: str | None = None) -> dict[str, Any] | None:
    packet = _candidate_cache_replay_packet()
    if not isinstance(packet, dict) or packet.get("status") == "cache_missing":
        return None
    receipt = packet.get("search_quant_projection_receipt") if isinstance(packet.get("search_quant_projection_receipt"), dict) else {}
    provider_receipt = (
        packet.get("search_quant_provider_model_acceptance_receipt")
        if isinstance(packet.get("search_quant_provider_model_acceptance_receipt"), dict)
        else {}
    )
    provider_task_id = _safe_text(provider_receipt.get("task_id"), limit=120)
    task_ids = [
        _safe_text(packet.get("task_id"), limit=120),
        _safe_text(receipt.get("latest_task_id"), limit=120),
        _safe_text(receipt.get("task_id"), limit=120),
        provider_task_id,
    ]
    task_ids = [item for item in task_ids if item]
    if not task_ids:
        return None
    selected_task_id = _safe_text(task_id, limit=120) if task_id else task_ids[0]
    if selected_task_id not in task_ids:
        return None
    selected_provider_acceptance = bool(provider_task_id and selected_task_id == provider_task_id)

    call_ledger: list[dict[str, Any]] = []
    seen: set[str] = set()
    provider_call_ledger = provider_receipt.get("provider_call_ledger") if isinstance(provider_receipt, dict) else []
    for row in (
        list(packet.get("call_ledger") or [])
        + list(receipt.get("call_ledger") or [])
        + list(provider_call_ledger or [])
    ):
        if not isinstance(row, dict):
            continue
        safe_row = _safe_value("call_ledger", row)
        if not isinstance(safe_row, dict):
            continue
        fingerprint = json.dumps(safe_row, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        call_ledger.append(safe_row)
    call_ledger_external_calls_replayed = any(
        row.get("external_calls_triggered") is True or row.get("external") is True for row in call_ledger
    )
    call_ledger_tushare_replayed = any(row.get("tushare_called") is True for row in call_ledger)
    call_ledger_deepseek_replayed = any(row.get("deepseek_called") is True for row in call_ledger)
    call_ledger_github_replayed = any(row.get("github_called") is True for row in call_ledger)

    latest_status = _safe_text(receipt.get("latest_task_status"), limit=32)
    status = latest_status if latest_status in TASK_STATUSES else "success"
    provider_ledger_ready = provider_receipt.get("tushare_call_ledger_evidence_done") is True
    current_step_source = (
        provider_receipt.get("status")
        if selected_provider_acceptance or provider_ledger_ready
        else receipt.get("latest_task_current_step") or receipt.get("status")
    )
    current_step = _safe_text(
        current_step_source
        or provider_receipt.get("status")
        or packet.get("search_quant_projection_status")
        or "candidate_radar_quant_projection_cache_replay",
        limit=160,
    )
    loaded_at = _safe_text(
        packet.get("search_quant_projection_completed_at")
        or packet.get("loaded_at")
        or packet.get("cache_api_loaded_at")
        or _now_iso(),
        limit=80,
    )
    record = build_task_record(
        "run_candidate_radar_quant_projection_provider_model_acceptance"
        if selected_provider_acceptance
        else "run_candidate_radar_quant_projection",
        task_id=selected_task_id,
        output_packet_key="command_center_3_candidate_radar_cache",
        payload={
            "source": "candidate_cache_replay",
            "source_packet_key": "command_center_3_candidate_radar_cache",
            "symbol": receipt.get("symbol") or provider_receipt.get("symbol"),
            "cache_replay_only": True,
            "readback_route": "GET /api/candidate-radar/cache",
            "replay_source_receipt": (
                "search_quant_provider_model_acceptance_receipt"
                if selected_provider_acceptance
                else "search_quant_projection_receipt"
            ),
            "does_not_create_task": True,
            "does_not_call_provider_from_readback": True,
        },
        status=status,
        progress=1.0 if status in TASK_TERMINAL_STATUSES else 0.5,
        current_step=current_step,
        warnings=[
            "该任务状态来自 CandidateRadar cache / packet 的只读回放；GET /api/tasks 不创建任务、不调用 Tushare、DeepSeek 或 GitHub。",
            "cache replay task 只帮助普通用户在任务目录看到最近搜票确认链；它不是新的生产验收证据。",
        ],
        call_ledger=call_ledger,
    )
    record.update(
        {
            "created_at": loaded_at,
            "started_at": loaded_at,
            "finished_at": loaded_at if status in TASK_TERMINAL_STATUSES else None,
            "backend": "candidate_cache_replay",
            "storage_source": "candidate_cache_replay",
            "cache_replay_only": True,
            "task_created_by_get": False,
            "readback_source": "command_center_3_candidate_radar_cache",
            "candidate_cache_replay_step_source": (
                "search_quant_provider_model_acceptance_receipt"
                if selected_provider_acceptance or provider_ledger_ready
                else "search_quant_projection_receipt"
            ),
            "call_ledger_external_calls_replayed": call_ledger_external_calls_replayed,
            "call_ledger_tushare_replayed": call_ledger_tushare_replayed,
            "call_ledger_deepseek_replayed": call_ledger_deepseek_replayed,
            "call_ledger_github_replayed": call_ledger_github_replayed,
            "source_task_external_calls_triggered": call_ledger_external_calls_replayed,
            "source_task_tushare_called": call_ledger_tushare_replayed,
            "source_task_deepseek_called": call_ledger_deepseek_replayed,
            "source_task_github_called": call_ledger_github_replayed,
            "source_task_provider_ledger_replayed": call_ledger_external_calls_replayed
            or call_ledger_tushare_replayed
            or call_ledger_deepseek_replayed
            or call_ledger_github_replayed,
            "call_ledger_replay_is_read_only": True,
            "readback_external_calls_triggered": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "status_history": [
                _status_event(
                    status,
                    progress=1.0 if status in TASK_TERMINAL_STATUSES else 0.5,
                    current_step=current_step,
                    at=loaded_at,
                )
            ],
            "task_log": [
                _task_log_event(
                    "task_cache_replayed",
                    status=status,
                    current_step=current_step,
                    message="candidate radar task id replayed from local cache without creating a task",
                    at=loaded_at,
                )
            ],
        }
    )
    return record


def _candidate_cache_latest_confirmed_readback() -> dict[str, Any]:
    packet = _candidate_cache_replay_packet()
    if not isinstance(packet, dict) or packet.get("status") == "cache_missing":
        return {}
    receipt = packet.get("search_quant_projection_receipt") if isinstance(packet.get("search_quant_projection_receipt"), dict) else {}
    provider_receipt = (
        packet.get("search_quant_provider_model_acceptance_receipt")
        if isinstance(packet.get("search_quant_provider_model_acceptance_receipt"), dict)
        else {}
    )
    symbol = _safe_text(
        packet.get("latest_confirmed_symbol")
        or receipt.get("symbol")
        or provider_receipt.get("symbol"),
        limit=32,
    )
    task_id = _safe_text(
        packet.get("latest_confirmed_task_id")
        or packet.get("search_quant_projection_latest_task_id")
        or receipt.get("latest_task_id")
        or receipt.get("task_id")
        or provider_receipt.get("task_id")
        or packet.get("task_id"),
        limit=120,
    )
    task_status = _safe_text(
        packet.get("latest_confirmed_task_status")
        or packet.get("latest_task_status")
        or receipt.get("latest_task_status")
        or provider_receipt.get("latest_task_status")
        or "",
        limit=32,
    )
    task_current_step = _safe_text(
        packet.get("latest_confirmed_task_current_step")
        or packet.get("latest_task_current_step")
        or receipt.get("latest_task_current_step")
        or provider_receipt.get("status")
        or receipt.get("status")
        or "",
        limit=160,
    )
    if not (symbol or task_id):
        return {}
    return {
        "schema_version": "command_center_task_status_latest_confirmed_readback.v1",
        "status": "ready",
        "source_packet_key": "command_center_3_candidate_radar_cache",
        "latest_confirmed_symbol": symbol,
        "latest_confirmed_symbol_source": "candidate_cache_task_status_index_readback",
        "latest_confirmed_task_id": task_id,
        "latest_confirmed_task_status": task_status,
        "latest_confirmed_task_current_step": task_current_step,
        "cache_only_readback": True,
        "creates_task_from_readback": False,
        "calls_provider_or_model": False,
        "readback_external_calls_triggered": False,
        "contains_secret": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _candidate_cache_replay_tasks() -> list[dict[str, Any]]:
    packet = _candidate_cache_replay_packet()
    if not isinstance(packet, dict) or packet.get("status") == "cache_missing":
        return []
    receipt = packet.get("search_quant_projection_receipt") if isinstance(packet.get("search_quant_projection_receipt"), dict) else {}
    provider_receipt = (
        packet.get("search_quant_provider_model_acceptance_receipt")
        if isinstance(packet.get("search_quant_provider_model_acceptance_receipt"), dict)
        else {}
    )
    task_ids: list[str] = []
    for raw_task_id in (
        packet.get("task_id"),
        receipt.get("latest_task_id"),
        receipt.get("task_id"),
        provider_receipt.get("task_id"),
    ):
        safe_task_id = _safe_text(raw_task_id, limit=120)
        if safe_task_id and safe_task_id not in task_ids:
            task_ids.append(safe_task_id)
    return [
        replay_task
        for replay_task in (_candidate_cache_replay_task(task_id) for task_id in task_ids)
        if replay_task is not None
    ]


def _active_duplicate_task(idempotency_key: str, *, exclude_task_id: str = "") -> dict[str, Any] | None:
    active_duplicates, _ = _idempotency_duplicates(idempotency_key, exclude_task_id=exclude_task_id)
    if not active_duplicates:
        return None
    return read_task_status(active_duplicates[0])


def _mark_task_reused_by_dedupe(task: dict[str, Any], *, candidate: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    task_type = str(candidate.get("task_type") or task.get("task_type") or "")
    input_hash = str(candidate.get("input_hash") or task.get("input_hash") or "")
    dedupe_policy = dict(task.get("dedupe_policy") if isinstance(task.get("dedupe_policy"), dict) else {})
    dedupe_policy.update(
        {
            "dispatch_dedupe_enforced": True,
            "audit_only": False,
            "auto_blocks_task_creation": True,
            "duplicate_detected": True,
            "reused_existing_task_id": task.get("task_id"),
            "blocked_duplicate_candidate_task_id": candidate.get("task_id"),
            "blocked_duplicate_creation_count": int(dedupe_policy.get("blocked_duplicate_creation_count") or 0) + 1,
            "note": "本地 dispatch 去重已复用同 task_type+payload 的非终态任务；不会创建重复任务、不会自动外联。",
        }
    )
    task["dedupe_policy"] = dedupe_policy
    lock_policy = dict(task.get("lock_policy") if isinstance(task.get("lock_policy"), dict) else {})
    lock_policy.update(
        {
            "lock_enforcement_enabled": TASK_LOCK_ENFORCED,
            "lock_enforced": True,
            "audit_only": False,
            "auto_blocks_task_creation": True,
            "lock_conflict_detected": True,
            "active_conflict_count": int(lock_policy.get("active_conflict_count") or 0) + 1,
            "blocked_duplicate_candidate_task_id": candidate.get("task_id"),
            "blocked_duplicate_creation_count": int(lock_policy.get("blocked_duplicate_creation_count") or 0) + 1,
            "reused_existing_task_id": task.get("task_id"),
            "note": "本地 dispatch 锁已复用同 task_type+payload 的非终态任务；不会创建并发重复任务、不会自动外联。",
        }
    )
    task["lock_policy"] = lock_policy
    task["lock_enforced"] = True
    task["dedupe_reused_existing"] = True
    task["dedupe_reuse_count"] = int(task.get("dedupe_reuse_count") or 0) + 1
    task.setdefault("warnings", []).append("task_creation_deduped_and_lock_reused_active_task_no_external_call")
    task.setdefault("call_ledger", []).append(
        _dedupe_reuse_call_ledger(str(task.get("task_id") or ""), now, task_type=task_type, input_hash=input_hash)
    )
    task.setdefault("call_ledger", []).append(
        _lock_reuse_call_ledger(str(task.get("task_id") or ""), now, task_type=task_type, input_hash=input_hash)
    )
    task.setdefault("task_log", []).append(
        _task_log_event(
            "task_creation_deduped_reused_active_task",
            status=str(task.get("status") or "pending"),
            current_step=str(task.get("current_step") or ""),
            message="reused active task with same task_type and sanitized payload",
            at=now,
        )
    )
    task["external_calls_triggered"] = False
    task["tushare_called"] = False
    task["deepseek_called"] = False
    task["github_called"] = False
    task["does_not_execute_trades"] = True
    task["does_not_modify_strategy_action"] = True
    return _persist_task(task)


def create_task_record(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "queued",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step=current_step,
        warnings=warnings,
    )
    if TASK_DISPATCH_DEDUPE_ENFORCED:
        duplicate = _active_duplicate_task(str(task.get("idempotency_key") or ""), exclude_task_id=str(task.get("task_id") or ""))
        if duplicate is not None:
            return _mark_task_reused_by_dedupe(duplicate, candidate=task)
    return _persist_task(task)


def update_task_status(
    task_id: str,
    *,
    status: str,
    progress: float | None = None,
    current_step: str | None = None,
    error_message_safe: str | None = None,
    output_packet_key: str | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
    warning: str | None = None,
) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None
    if status not in TASK_STATUSES:
        status = "failed"
        error_message_safe = error_message_safe or "invalid_task_status"
    now = _now_iso()
    task["status"] = status
    if progress is not None:
        task["progress"] = max(0.0, min(1.0, float(progress)))
    if current_step is not None:
        task["current_step"] = current_step
    if error_message_safe is not None:
        task["error_message_safe"] = _safe_text(error_message_safe)
    if output_packet_key is not None:
        task["output_packet_key"] = output_packet_key
    if call_ledger is not None:
        task["call_ledger"] = list(call_ledger)
        task["external_calls_triggered"] = any(row.get("external_calls_triggered") is True or row.get("external") is True for row in task["call_ledger"])
        task["tushare_called"] = any(row.get("tushare_called") is True for row in task["call_ledger"])
        task["deepseek_called"] = any(row.get("deepseek_called") is True for row in task["call_ledger"])
        task["github_called"] = any(row.get("github_called") is True for row in task["call_ledger"])
        task["does_not_execute_trades"] = all(row.get("does_not_execute_trades") is not False for row in task["call_ledger"])
        task["does_not_modify_strategy_action"] = all(row.get("does_not_modify_strategy_action") is not False for row in task["call_ledger"])
    if warning:
        task.setdefault("warnings", []).append(warning)
    old_retry_policy = task.get("retry_policy") if isinstance(task.get("retry_policy"), dict) else {}
    task["dedupe_policy"] = _dedupe_policy_for_task(
        str(task.get("task_type") or ""),
        task_id=str(task.get("task_id") or ""),
        input_hash=str(task.get("input_hash") or ""),
        idempotency_key=str(task.get("idempotency_key") or ""),
    )
    task["lock_policy"] = _lock_policy_for_task(
        str(task.get("task_type") or ""),
        task_id=str(task.get("task_id") or ""),
        input_hash=str(task.get("input_hash") or ""),
        lock_key=str(task.get("lock_key") or ""),
        status=status,
    )
    task["retry_policy"] = _retry_policy_for_task(
        str(task.get("task_type") or ""),
        status=status,
        attempt_number=old_retry_policy.get("attempt_number") if isinstance(old_retry_policy, dict) else None,
    )
    if status in {"running", "success", "failed"} and not task.get("started_at"):
        task["started_at"] = now
    if status in {"success", "failed", "cancelled"}:
        task["finished_at"] = now
    task.setdefault("status_history", []).append(
        _status_event(status, progress=float(task.get("progress") or 0.0), current_step=str(task.get("current_step") or ""), at=now)
    )
    task.setdefault("task_log", []).append(
        _task_log_event(
            "task_status_updated",
            status=status,
            current_step=str(task.get("current_step") or ""),
            message=error_message_safe or warning or "local task status updated",
            at=now,
        )
    )
    return _persist_task(task)


def cancel_task(task_id: str, payload: Any = None) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None

    payload_safe = _safe_payload(payload)
    reason_safe = _safe_text(payload_safe.get("reason", "")) if isinstance(payload_safe, dict) else ""
    now = _now_iso()
    existing_ledger = list(task.get("call_ledger") or [])
    cancel_ledger = existing_ledger + [_cancel_call_ledger(str(task_id), now, reason_safe=reason_safe)]
    terminal = {"success", "failed", "cancelled"}
    if task.get("status") in terminal:
        task["call_ledger"] = cancel_ledger
        task.setdefault("warnings", []).append("task_cancel_noop_already_terminal")
        task.setdefault("task_log", []).append(
            _task_log_event(
                "task_cancel_noop_already_terminal",
                status=str(task.get("status") or "unknown"),
                current_step=str(task.get("current_step") or ""),
                message=reason_safe,
                at=now,
            )
        )
        task["external_calls_triggered"] = False
        task["deepseek_called"] = False
        task["tushare_called"] = False
        task["github_called"] = False
        task["does_not_execute_trades"] = True
        task["does_not_modify_strategy_action"] = True
        return _persist_task(task)

    return update_task_status(
        str(task_id),
        status="cancelled",
        progress=float(task.get("progress") or 0.0),
        current_step="cancelled_by_user_no_external_call",
        error_message_safe="",
        call_ledger=cancel_ledger,
        warning="task_cancelled_locally_no_external_call",
    )


def retry_task(task_id: str, payload: Any = None) -> dict[str, Any] | None:
    source = read_task_status(task_id)
    if source is None:
        return None

    payload_safe = _safe_payload(payload)
    reason_safe = _safe_text(payload_safe.get("reason", "")) if isinstance(payload_safe, dict) else ""
    now = _now_iso()
    source_policy = source.get("retry_policy") if isinstance(source.get("retry_policy"), dict) else {}
    task_type = str(source.get("task_type") or "")
    retry_policy = _retry_policy_for_task(
        task_type,
        status=str(source.get("status") or ""),
        attempt_number=source_policy.get("attempt_number") if isinstance(source_policy, dict) else None,
    )
    if not retry_policy.get("manual_retry_eligible"):
        ledger = [_retry_call_ledger(str(task_id), now, call_status="manual_retry_not_eligible_no_external_call", reason_safe=reason_safe)]
        source.setdefault("warnings", []).append("manual_retry_not_eligible_no_external_call")
        source.setdefault("task_log", []).append(
            _task_log_event(
                "manual_retry_not_eligible",
                status=str(source.get("status") or "unknown"),
                current_step=str(source.get("current_step") or ""),
                message=reason_safe or "manual retry rejected by retry policy",
                at=now,
            )
        )
        source["call_ledger"] = list(source.get("call_ledger") or []) + ledger
        source["external_calls_triggered"] = False
        source["tushare_called"] = False
        source["deepseek_called"] = False
        source["github_called"] = False
        source["does_not_execute_trades"] = True
        source["does_not_modify_strategy_action"] = True
        _persist_task(source)
        return {
            "ok": False,
            "error": "manual_retry_not_eligible",
            "task": source,
            "call_ledger": ledger,
            "warnings": ["manual retry 只允许 failed 且仍有 attempts_remaining 的任务；不会自动外联或交易。"],
        }

    attempt_number = int(retry_policy.get("attempt_number") or 1) + 1
    new_task = build_task_record(
        task_type,
        output_packet_key=str(source.get("output_packet_key") or ""),
        payload=source.get("payload_safe") or {},
        status="pending",
        progress=0.0,
        current_step="manual_retry_queued_no_external_call",
        warnings=[
            "manual retry 仅创建新的本地任务记录；不会在 retry 路由中自动调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
            f"source_task_id={_safe_text(task_id, limit=120)}",
        ],
    )
    retry_ledger = [_retry_call_ledger(str(task_id), now, new_task_id=str(new_task["task_id"]), reason_safe=reason_safe)]
    new_task["retry_source_task_id"] = str(task_id)
    new_task["retry_created_by"] = "POST /api/tasks/{task_id}/retry"
    new_task["retry_policy"] = _retry_policy_for_task(task_type, status="pending", attempt_number=attempt_number)
    new_task["call_ledger"] = retry_ledger
    new_task["external_calls_triggered"] = False
    new_task["tushare_called"] = False
    new_task["deepseek_called"] = False
    new_task["github_called"] = False
    new_task["does_not_execute_trades"] = True
    new_task["does_not_modify_strategy_action"] = True
    new_task.setdefault("task_log", []).append(
        _task_log_event(
            "manual_retry_task_created",
            status="pending",
            current_step="manual_retry_queued_no_external_call",
            message=reason_safe or "manual retry task created without external work",
            at=now,
        )
    )
    persisted_new = _persist_task(new_task)
    source.setdefault("task_log", []).append(
        _task_log_event(
            "manual_retry_spawned_new_task",
            status=str(source.get("status") or ""),
            current_step=str(source.get("current_step") or ""),
            message=f"new_task_id={persisted_new['task_id']}",
            at=now,
        )
    )
    source.setdefault("warnings", []).append("manual_retry_spawned_new_task_no_external_call")
    _persist_task(source)
    return {
        "ok": True,
        "task": persisted_new,
        "source_task": source,
        "call_ledger": retry_ledger,
        "warnings": persisted_new.get("warnings") or [],
    }


def create_task_stub(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "stub_created_no_external_call",
) -> dict[str, Any]:
    now = _now_iso()
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step="queued",
        warnings=["Command Center 3.0 MVP 任务接口为本地 lifecycle stub；没有调用 Tushare、DeepSeek、GitHub 或真实交易接口。"],
    )
    if TASK_DISPATCH_DEDUPE_ENFORCED:
        duplicate = _active_duplicate_task(str(task.get("idempotency_key") or ""), exclude_task_id=str(task.get("task_id") or ""))
        if duplicate is not None:
            return _mark_task_reused_by_dedupe(duplicate, candidate=task)
    _persist_task(task)
    update_task_status(task["task_id"], status="running", progress=0.5, current_step="local_fallback_running")
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=current_step,
        call_ledger=_stub_call_ledger(task_type, now),
    ) or task


def read_task_status(task_id: str) -> dict[str, Any] | None:
    task_key = str(task_id)
    memory_task = _TASKS.get(task_key)
    persisted_task = _read_persisted_task(task_key)
    if memory_task is not None:
        row = dict(memory_task)
        row["storage_source"] = "memory_and_sqlite" if persisted_task is not None else "memory"
        return row
    if persisted_task is not None:
        row = dict(persisted_task)
        row["storage_source"] = "sqlite_meta"
        return row
    replay_task = _candidate_cache_replay_task(task_key)
    if replay_task is not None:
        return replay_task
    return None


def read_latest_task_status_by_type(
    task_type: str,
    *,
    include_history_fallback: bool = False,
    expected_history_receipt_key: str | None = None,
    expected_history_receipt_schema_version: str | None = None,
) -> dict[str, Any] | None:
    """Read the latest live task of a type, optionally falling back to history.

    History rows are read-only evidence projections. They are never copied into
    memory or the live ``task_status`` table.
    """

    task_type_key = str(task_type or "")
    live_task = next(
        (
            task
            for task in list_task_statuses()
            if str(task.get("task_type") or "") == task_type_key
        ),
        None,
    )
    if live_task is not None or not include_history_fallback or not SQLITE_META_PATH.exists():
        return live_task
    if not expected_history_receipt_key or not expected_history_receipt_schema_version:
        return {
            "task_id": None,
            "task_type": task_type_key,
            "status": "history_integrity_failed_safe",
            "current_step": "historical_evidence_rejected",
            "storage_source": "sqlite_task_status_history_invalid",
            "historical_evidence": True,
            "current_actionable": False,
            "history_integrity_valid": False,
            "history_integrity_error": "history_receipt_binding_not_declared",
            "history_updated_at": None,
            "history_payload_digest": None,
        }
    try:
        return SQLiteMetaStore(SQLITE_META_PATH, read_only=True).read_latest_task_status_history_by_type(
            task_type_key,
            expected_receipt_key=expected_history_receipt_key,
            expected_receipt_schema_version=expected_history_receipt_schema_version,
        )
    except Exception:
        return {
            "task_id": None,
            "task_type": task_type_key,
            "status": "history_integrity_failed_safe",
            "current_step": "historical_evidence_rejected",
            "storage_source": "sqlite_task_status_history_invalid",
            "historical_evidence": True,
            "current_actionable": False,
            "history_integrity_valid": False,
            "history_integrity_error": "history_lookup_failed_safe",
            "history_updated_at": None,
            "history_payload_digest": None,
        }


def _merge_task_statuses() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    persisted_tasks = _list_persisted_tasks()
    persisted_ids = {str(task.get("task_id") or "") for task in persisted_tasks if task.get("task_id")}
    memory_ids = {str(task_id) for task_id in _TASKS}
    shared_ids = persisted_ids & memory_ids

    merged: dict[str, dict[str, Any]] = {}
    for task in persisted_tasks:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        row = dict(task)
        row["storage_source"] = "sqlite_meta"
        merged[task_id] = row
    for task_id, task in _TASKS.items():
        row = dict(task)
        row["storage_source"] = "memory_and_sqlite" if str(task_id) in persisted_ids else "memory"
        merged[str(task_id)] = row
    replay_tasks = _candidate_cache_replay_tasks()
    replay_task_count = 0
    for replay_task in replay_tasks:
        replay_task_id = str(replay_task.get("task_id") or "")
        if replay_task_id and replay_task_id not in merged:
            merged[replay_task_id] = replay_task
            replay_task_count += 1

    sorted_tasks = sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("started_at") or item.get("created_at") or ""),
        reverse=True,
    )
    persistence = {
        "task_rows_include_idempotency_key": True,
        "task_rows_include_dedupe_policy": True,
        "task_rows_include_lock_key": True,
        "task_rows_include_lock_policy": True,
        "task_rows_include_retry_policy": True,
        "task_rows_include_task_log": True,
        "storage_backend": "memory_plus_sqlite_fallback",
        "sqlite_fallback_enabled": True,
        "sqlite_meta_path_label": ".stock_ming_3/meta.sqlite",
        "memory_task_count": len(memory_ids),
        "sqlite_task_count": len(persisted_ids),
        "deduplicated_task_count": len(sorted_tasks),
        "idempotency_key_count": len({str(task.get("idempotency_key") or "") for task in sorted_tasks if task.get("idempotency_key")}),
        "duplicate_idempotency_key_count": max(
            0,
            len([task for task in sorted_tasks if task.get("idempotency_key")])
            - len({str(task.get("idempotency_key") or "") for task in sorted_tasks if task.get("idempotency_key")}),
        ),
        "dedupe_duplicate_audit_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("dedupe_policy"), dict)
            and task.get("dedupe_policy", {}).get("duplicate_detected") is True
        ),
        "dispatch_dedupe_enforced_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("dedupe_policy"), dict)
            and task.get("dedupe_policy", {}).get("dispatch_dedupe_enforced") is True
        ),
        "dedupe_blocked_creation_count": sum(
            int(task.get("dedupe_policy", {}).get("blocked_duplicate_creation_count") or 0)
            for task in sorted_tasks
            if isinstance(task.get("dedupe_policy"), dict)
        ),
        "lock_blocked_creation_count": sum(
            int(task.get("lock_policy", {}).get("blocked_duplicate_creation_count") or 0)
            for task in sorted_tasks
            if isinstance(task.get("lock_policy"), dict)
        ),
        "manual_retry_eligible_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("retry_policy"), dict)
            and task.get("retry_policy", {}).get("manual_retry_eligible") is True
        ),
        "automatic_retry_enabled_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("retry_policy"), dict)
            and task.get("retry_policy", {}).get("auto_retry_enabled") is True
        ),
        "lock_conflict_audit_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("lock_policy"), dict)
            and task.get("lock_policy", {}).get("lock_conflict_detected") is True
        ),
        "lock_enforced_task_count": sum(
            1
            for task in sorted_tasks
            if isinstance(task.get("lock_policy"), dict)
            and task.get("lock_policy", {}).get("lock_enforced") is True
        ),
        "task_log_count": sum(len(task.get("task_log") or []) for task in sorted_tasks),
        "memory_only_task_count": len(memory_ids - persisted_ids),
        "sqlite_only_task_count": len(persisted_ids - memory_ids),
        "memory_and_sqlite_task_count": len(shared_ids),
        "candidate_cache_replay_task_count": replay_task_count,
        "task_rows_include_storage_source": True,
        "cache_read_external_calls": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return sorted_tasks, persistence


@memoize_request_local_read("task_status_list")
def list_task_statuses() -> list[dict[str, Any]]:
    tasks, _ = _merge_task_statuses()
    return tasks


def build_task_status_index() -> dict[str, Any]:
    tasks, persistence = _merge_task_statuses()
    status_counts = {status: 0 for status in sorted(TASK_STATUSES)}
    for task in tasks:
        status = str(task.get("status") or "pending")
        status_counts[status] = status_counts.get(status, 0) + 1
    call_ledger_count = sum(len(task.get("call_ledger") or []) for task in tasks)
    external_calls_triggered = any(task.get("external_calls_triggered") is True for task in tasks)
    tushare_called = any(task.get("tushare_called") is True for task in tasks)
    deepseek_called = any(task.get("deepseek_called") is True for task in tasks)
    github_called = any(task.get("github_called") is True for task in tasks)
    call_ledger_external_calls_replayed = any(
        task.get("call_ledger_external_calls_replayed") is True
        or any(
            isinstance(row, dict)
            and (row.get("external_calls_triggered") is True or row.get("external") is True)
            for row in (task.get("call_ledger") or [])
        )
        for task in tasks
    )
    call_ledger_tushare_replayed = any(
        task.get("call_ledger_tushare_replayed") is True
        or any(
            isinstance(row, dict) and row.get("tushare_called") is True
            for row in (task.get("call_ledger") or [])
        )
        for task in tasks
    )
    call_ledger_deepseek_replayed = any(
        task.get("call_ledger_deepseek_replayed") is True
        or any(
            isinstance(row, dict) and row.get("deepseek_called") is True
            for row in (task.get("call_ledger") or [])
        )
        for task in tasks
    )
    call_ledger_github_replayed = any(
        task.get("call_ledger_github_replayed") is True
        or any(
            isinstance(row, dict) and row.get("github_called") is True
            for row in (task.get("call_ledger") or [])
        )
        for task in tasks
    )
    does_not_execute_trades = all(task.get("does_not_execute_trades") is not False for task in tasks)
    does_not_modify_strategy_action = all(task.get("does_not_modify_strategy_action") is not False for task in tasks)
    task_log_count = sum(len(task.get("task_log") or []) for task in tasks)
    latest_task = tasks[0] if tasks else {}
    latest_confirmed_readback = _candidate_cache_latest_confirmed_readback()
    return {
        "packet_key": "command_center_3_task_status_index",
        "schema_version": "command_center_3_task_status_index.v1",
        "mode": "cache_only",
        "status": "ready",
        "tasks": tasks,
        "task_count": len(tasks),
        "status_counts": status_counts,
        "latest_task_id": latest_task.get("task_id"),
        "latest_task_type": latest_task.get("task_type"),
        "latest_task_status": latest_task.get("status"),
        "latest_confirmed_symbol": latest_confirmed_readback.get("latest_confirmed_symbol"),
        "latest_confirmed_symbol_source": latest_confirmed_readback.get("latest_confirmed_symbol_source"),
        "latest_confirmed_task_id": latest_confirmed_readback.get("latest_confirmed_task_id"),
        "latest_confirmed_task_status": latest_confirmed_readback.get("latest_confirmed_task_status"),
        "latest_confirmed_task_current_step": latest_confirmed_readback.get("latest_confirmed_task_current_step"),
        "latest_confirmed_symbol_readback_external_calls_triggered": False,
        "latest_confirmed_symbol_creates_task_from_readback": False,
        "call_ledger_count": call_ledger_count,
        "task_log_count": task_log_count,
        "persistence": persistence,
        "persistence_source_rows": [
            {"source": "memory", "task_count": persistence["memory_task_count"], "external": False},
            {"source": "sqlite_meta", "task_count": persistence["sqlite_task_count"], "external": False},
            {"source": "deduplicated", "task_count": persistence["deduplicated_task_count"], "external": False},
        ] + (
            [
                {
                    "source": "candidate_cache_replay",
                    "task_count": persistence["candidate_cache_replay_task_count"],
                    "external": False,
                }
            ]
            if persistence.get("candidate_cache_replay_task_count")
            else []
        ),
        "policy": {
            "get_tasks_cache_only": True,
            "does_not_create_tasks": True,
            "does_not_call_external_sources": True,
            "reads_memory_and_sqlite_fallback": True,
            "reads_candidate_cache_task_replay": True,
            "candidate_cache_replay_creates_task": False,
            "candidate_cache_replay_calls_external_sources": False,
            "latest_confirmed_readback_is_cache_only": True,
            "latest_confirmed_readback_creates_task": False,
            "latest_confirmed_readback_calls_external_sources": False,
            "latest_confirmed_readback_is_not_trade_signal": True,
            "call_ledger_replay_is_read_only": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "task_logs_safe": True,
            "task_logs_include_no_raw_payload": True,
        },
        "external_calls_triggered": external_calls_triggered,
        "tushare_called": tushare_called,
        "deepseek_called": deepseek_called,
        "github_called": github_called,
        "call_ledger_external_calls_replayed": call_ledger_external_calls_replayed,
        "call_ledger_tushare_replayed": call_ledger_tushare_replayed,
        "call_ledger_deepseek_replayed": call_ledger_deepseek_replayed,
        "call_ledger_github_replayed": call_ledger_github_replayed,
        "readback_external_calls_triggered": False,
        "does_not_execute_trades": does_not_execute_trades,
        "does_not_modify_strategy_action": does_not_modify_strategy_action,
        "call_ledger": [
            {
                "api": "local_task_status_index",
                "request_params_safe": {},
                "row_count": len(tasks),
                "memory_task_count": persistence["memory_task_count"],
                "sqlite_task_count": persistence["sqlite_task_count"],
                "deduplicated_task_count": persistence["deduplicated_task_count"],
                "idempotency_key_count": persistence["idempotency_key_count"],
                "duplicate_idempotency_key_count": persistence["duplicate_idempotency_key_count"],
                "dedupe_duplicate_audit_count": persistence["dedupe_duplicate_audit_count"],
                "dispatch_dedupe_enforced_count": persistence["dispatch_dedupe_enforced_count"],
                "dedupe_blocked_creation_count": persistence["dedupe_blocked_creation_count"],
                "lock_blocked_creation_count": persistence["lock_blocked_creation_count"],
                "manual_retry_eligible_count": persistence["manual_retry_eligible_count"],
                "automatic_retry_enabled_count": persistence["automatic_retry_enabled_count"],
                "lock_conflict_audit_count": persistence["lock_conflict_audit_count"],
                "lock_enforced_task_count": persistence["lock_enforced_task_count"],
                "task_log_count": task_log_count,
                "storage_backend": persistence["storage_backend"],
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "GET /api/tasks 只读取本地任务状态；不会调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。",
            "任务明细中的 payload_safe 已在创建任务时剔除 token/api_key/authorization 等敏感字段。",
        ],
    }


def clear_task_statuses_for_tests(*, clear_persisted: bool = False) -> None:
    _TASKS.clear()
    if not clear_persisted:
        return
    meta_path = Path(SQLITE_META_PATH).resolve()
    if meta_path == DEFAULT_SQLITE_META_PATH.resolve():
        raise RuntimeError("refusing_to_clear_default_sqlite_task_statuses")
    try:
        SQLiteMetaStore(meta_path).clear_task_statuses()
    except Exception:
        return
