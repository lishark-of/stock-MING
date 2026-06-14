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


_TASKS: dict[str, dict[str, Any]] = {}
TASK_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
SECRET_KEYWORDS = ("token", "api_key", "secret", "password", "authorization", "bearer", "cookie")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
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
        "provider_acceptance_modes": ["provider_backed_trade_cal_long_window", "provider_target_sample_acceptance"],
        "trade_cal_provider_acceptance_mode_requires_explicit_payload": True,
        "trade_cal_provider_acceptance_requires_long_window_days": 730,
        "trade_cal_provider_acceptance_requires_failure_mode_evidence": True,
        "trade_cal_provider_acceptance_requires_freshness_replay": True,
        "trade_cal_provider_acceptance_is_full_interface_acceptance": False,
        "full_interface_acceptance_done": False,
        "cache_get_external_calls": False,
        "call_ledger_required": True,
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
        "task_type": "run_factor_light",
        "route": "POST /api/factor-quant/run-light",
        "label": "运行 light mode 因子计算",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_light_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "universe_modes": ["current_target"],
        "future_universe_modes": ["watchlist", "custom_pool", "full_pool"],
        "factor_universe_contract_status": "current_target_only_local_light_pipeline",
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
    "run_candidate_radar_quick_scan": {
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
    "run_motion_browser_qa_review": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
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
    "run_storage_schema_validation_acceptance": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
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
    "run_storage_compaction_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_storage_cache_ttl_dry_run": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
    },
    "run_worker_synthetic_healthcheck": {
        "manual_retry_allowed": True,
        "max_attempts": 2,
        "backoff": "manual_linear_15s_60s",
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
    return _dt.datetime.now().isoformat(timespec="seconds")


def _build_route_coverage() -> dict[str, Any]:
    task_routes = [str(item.get("route") or "") for item in TASK_CATALOG]
    lifecycle_routes = [str(item.get("route") or "") for item in TASK_LIFECYCLE_POST_ROUTES]
    known_post_routes = task_routes + lifecycle_routes
    return {
        "status": "ready",
        "scope": "command_center_3_button_gated_post_routes",
        "task_creation_route_count": len(task_routes),
        "local_lifecycle_route_count": len(lifecycle_routes),
        "known_post_route_count": len(known_post_routes),
        "task_creation_routes": task_routes,
        "local_lifecycle_routes": lifecycle_routes,
        "known_post_routes": known_post_routes,
        "uncovered_post_routes": [],
        "all_known_post_routes_button_gated": all(bool(item.get("button_gated")) for item in TASK_CATALOG + TASK_LIFECYCLE_POST_ROUTES),
        "call_ledger_required_for_all_known_post_routes": all(
            bool(item.get("call_ledger_required")) for item in TASK_CATALOG + TASK_LIFECYCLE_POST_ROUTES
        ),
        "cache_reads_create_no_tasks": True,
        "cancel_routes_external_calls": False,
        "retry_routes_external_calls": False,
        "lifecycle_routes_external_calls": False,
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
        if "pipeline" in backend:
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
    try:
        task = SQLiteMetaStore(SQLITE_META_PATH).read_task_status(str(task_id))
    except Exception:
        return None
    return task if isinstance(task, dict) else None


def _list_persisted_tasks() -> list[dict[str, Any]]:
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH)
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
    return None


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
        "task_rows_include_storage_source": True,
        "cache_read_external_calls": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return sorted_tasks, persistence


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
    does_not_execute_trades = all(task.get("does_not_execute_trades") is not False for task in tasks)
    does_not_modify_strategy_action = all(task.get("does_not_modify_strategy_action") is not False for task in tasks)
    task_log_count = sum(len(task.get("task_log") or []) for task in tasks)
    latest_task = tasks[0] if tasks else {}
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
        "call_ledger_count": call_ledger_count,
        "task_log_count": task_log_count,
        "persistence": persistence,
        "persistence_source_rows": [
            {"source": "memory", "task_count": persistence["memory_task_count"], "external": False},
            {"source": "sqlite_meta", "task_count": persistence["sqlite_task_count"], "external": False},
            {"source": "deduplicated", "task_count": persistence["deduplicated_task_count"], "external": False},
        ],
        "policy": {
            "get_tasks_cache_only": True,
            "does_not_create_tasks": True,
            "does_not_call_external_sources": True,
            "reads_memory_and_sqlite_fallback": True,
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
    try:
        SQLiteMetaStore(SQLITE_META_PATH).clear_task_statuses()
    except Exception:
        return
