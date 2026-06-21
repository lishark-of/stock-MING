import os
from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


COMMAND_CENTER_RUNTIME_MODES = ("cache_only", "manual", "live_light", "live_full")
COMMAND_CENTER_DEFAULT_RUNTIME_MODE = "cache_only"
COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES = ("plan_only", "light_provider", "light_provider_model")
COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE = "plan_only"
COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES = (
    "bootstrap_only",
    "provider_factor_next",
    "provider_factor_next_model",
)
COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE = "provider_factor_next_model"
COMMAND_CENTER_RUNTIME_MODE_POLICIES = (
    {
        "mode": "cache_only",
        "default": True,
        "external_call_rule": "none",
        "task_creation_rule": "no_task_from_startup_render_get_cache_or_search",
        "startup_rule": "read_existing_cache_only",
        "fastapi_startup_rule": "no_provider_model_worker_trade_or_task_creation",
        "search_typing_rule": "no_task_provider_model_call_config_write_or_cache_write",
        "cache_get_rule": "read_only_no_provider_model_worker_or_trade",
        "react_render_rule": "read_only_no_provider_model_worker_or_trade",
        "ledger_rule": "no_external_call_no_ledger_required",
        "ordinary_entrance_visibility_rule": "show_task_boundary_in_user_summary_before_settings_developer_audit",
        "ordinary_mode_banner_rule": "read_only_status_banner_not_task_launcher_or_config_writer",
        "configured_switch_rule": "configured_true_is_operator_intent_not_effective_external_call",
        "effective_external_call_rule": "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
        "production_evidence_rule": "config_policy_row_is_not_production_evidence",
        "use_case": "smoke_ci_quick_view_offline_review",
    },
    {
        "mode": "manual",
        "default": False,
        "external_call_rule": "explicit_post_task_only",
        "task_creation_rule": "button_or_explicit_payload_only",
        "startup_rule": "page_open_and_search_do_not_autostart",
        "fastapi_startup_rule": "no_provider_model_worker_trade_or_task_creation",
        "search_typing_rule": "no_task_provider_model_call_config_write_or_cache_write",
        "cache_get_rule": "read_only_no_provider_model_worker_or_trade",
        "react_render_rule": "read_only_no_provider_model_worker_or_trade",
        "ledger_rule": "call_ledger_and_model_ledger_required_for_external_work",
        "ordinary_entrance_visibility_rule": "show_task_boundary_in_user_summary_before_settings_developer_audit",
        "ordinary_mode_banner_rule": "read_only_status_banner_not_task_launcher_or_config_writer",
        "configured_switch_rule": "configured_true_is_operator_intent_not_effective_external_call",
        "effective_external_call_rule": "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
        "production_evidence_rule": "config_policy_row_is_not_production_evidence",
        "use_case": "operator_controlled_research_acceptance",
    },
    {
        "mode": "live_light",
        "default": False,
        "external_call_rule": "auditable_background_post_task_worker_or_local_fallback",
        "task_creation_rule": "after_cache_render_rate_limited_local_task_only",
        "startup_rule": "cache_first_then_optional_bounded_background_task",
        "fastapi_startup_rule": "no_provider_model_worker_trade_or_task_creation",
        "search_typing_rule": "no_task_provider_model_call_config_write_or_cache_write",
        "cache_get_rule": "read_only_no_provider_model_worker_or_trade",
        "react_render_rule": "read_only_no_provider_model_worker_or_trade",
        "ledger_rule": "call_ledger_and_model_ledger_required_for_external_work",
        "ordinary_entrance_visibility_rule": "show_task_boundary_in_user_summary_before_settings_developer_audit",
        "ordinary_mode_banner_rule": "read_only_status_banner_not_task_launcher_or_config_writer",
        "configured_switch_rule": "configured_true_is_operator_intent_not_effective_external_call",
        "effective_external_call_rule": "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
        "production_evidence_rule": "config_policy_row_is_not_production_evidence",
        "use_case": "local_daily_light_research_client",
    },
    {
        "mode": "live_full",
        "default": False,
        "external_call_rule": "reserved_future_authorization",
        "task_creation_rule": "disabled_until_separate_authorization",
        "startup_rule": "reserved_no_startup_task",
        "fastapi_startup_rule": "no_provider_model_worker_trade_or_task_creation",
        "search_typing_rule": "no_task_provider_model_call_config_write_or_cache_write",
        "cache_get_rule": "read_only_no_provider_model_worker_or_trade",
        "react_render_rule": "read_only_no_provider_model_worker_or_trade",
        "ledger_rule": "reserved_future_authorization_required",
        "ordinary_entrance_visibility_rule": "show_task_boundary_in_user_summary_before_settings_developer_audit",
        "ordinary_mode_banner_rule": "read_only_status_banner_not_task_launcher_or_config_writer",
        "configured_switch_rule": "configured_true_is_operator_intent_not_effective_external_call",
        "effective_external_call_rule": "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
        "production_evidence_rule": "config_policy_row_is_not_production_evidence",
        "use_case": "reserved_full_pool_deep_scan",
    },
)

COMMAND_CENTER_RUNTIME_CONFIG_NAMES = (
    "COMMAND_CENTER_BOOTSTRAP_MODE",
    "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
    "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
    "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
    "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART",
    "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
    "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE",
    "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT",
    "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
    "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
    "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
)

COMMAND_CENTER_RUNTIME_MODE_CONFIG_CONTRACT = {
    "schema_version": "command_center_runtime_mode_config_contract.v1",
    "config_key": "COMMAND_CENTER_BOOTSTRAP_MODE",
    "default_mode": COMMAND_CENTER_DEFAULT_RUNTIME_MODE,
    "read_function": "get_command_center_runtime_mode_state()",
    "status_surface": "GET /api/bootstrap/status read-only operator context",
    "invalid_value_rule": "redact_invalid_value_and_fallback_to_cache_only",
    "frontend_visibility_rule": "read_only_mode_banner_no_frontend_edit_or_writeback",
    "fastapi_startup_rule": "no_provider_model_worker_trade_or_task_creation",
    "search_typing_rule": "no_task_provider_model_call_config_write_or_cache_write",
    "cache_get_rule": "read_only_no_provider_model_worker_or_trade",
    "react_render_rule": "read_only_no_provider_model_worker_or_trade",
    "manual_rule": "explicit_button_or_post_task_only",
    "live_light_rule": "after_cache_render_may_create_bounded_local_post_task_only",
    "live_full_rule": "reserved_disabled_requires_separate_authorization",
    "configured_switch_rule": "configured_true_is_operator_intent_not_effective_external_call",
    "effective_external_call_rule": (
        "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion"
    ),
    "live_light_completion_rule": "runtime_config_does_not_prove_full_live_light_workflow",
    "production_evidence_rule": "runtime_config_contract_is_not_production_evidence",
    "contains_secret": False,
    "external_calls_triggered": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_LIVE_LIGHT_BOOTSTRAP_TASK_CONTRACT = {
    "schema_version": "command_center_live_light_bootstrap_task_contract.v1",
    "mode": "live_light",
    "task_route": "POST /api/bootstrap/live-startup",
    "task_type": "command_center_live_bootstrap",
    "task_status_route": "GET /api/tasks/{task_id}",
    "trigger_surface": "after_initial_cache_render_only",
    "mode_gate": "COMMAND_CENTER_BOOTSTRAP_MODE=live_light",
    "startup_autostart_config_key": "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART",
    "source_switch_config_keys": (
        "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
        "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
    ),
    "external_execution_profile_config_key": "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
    "research_scope_config_key": "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE",
    "rate_limit_config_key": "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
    "symbol_limit_config_key": "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
    "task_creation_rule": "create_or_reuse_one_rate_limited_local_task_after_cache_render",
    "queue_budget_rule": "one_active_or_recent_task_per_session_and_rate_window",
    "cache_first_rule": "render_existing_cache_before_task_creation",
    "ui_rule": "nonblocking_status_polling_with_last_successful_cache_fallback",
    "manual_mode_rule": "manual_mode_requires_explicit_button_or_post_task",
    "cache_only_rule": "cache_only_never_creates_bootstrap_task",
    "live_full_rule": "live_full_reserved_disabled_no_bootstrap_task",
    "search_typing_rule": "search_typing_never_creates_bootstrap_task",
    "provider_model_execution_rule": "future_provider_model_execution_requires_execution_request_and_ledgers",
    "production_evidence_rule": "bootstrap_task_contract_is_not_execution_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT = {
    "schema_version": "command_center_search_quant_projection_task_contract.v1",
    "ordinary_entrance": "Stock Quant Projection / Candidate Radar searched-symbol submit",
    "next_click_label": "生成 3.0 量化推演",
    "task_route": "POST /api/candidate-radar/quant-projection",
    "task_type": "run_candidate_radar_quant_projection",
    "task_status_route": "GET /api/tasks/{task_id}",
    "output_packet_key": "command_center_3_candidate_radar_cache",
    "receipt_schema_version": "candidate_radar_search_quant_projection_receipt.v1",
    "trigger_surface": "explicit_confirmed_symbol_submit_or_live_light_safe_submit",
    "mode_gate_rule": "manual_explicit_button_or_live_light_effective_search_submit_autostart",
    "search_submit_autostart_config_key": "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
    "symbol_rule": "confirmed_single_a_share_symbol_normalize_suffix_and_drop_raw_query",
    "typing_rule": "search_typing_never_creates_task",
    "cache_get_rule": "get_candidate_radar_cache_replays_latest_status_only",
    "task_creation_rule": "create_or_reuse_local_quant_projection_receipt_task_only",
    "acceptance_dry_run_route": "POST /api/candidate-radar/quant-projection-acceptance-dry-run",
    "execution_request_route": "POST /api/candidate-radar/quant-projection-execution-request",
    "provider_model_acceptance_route": "POST /api/candidate-radar/quant-projection-provider-model-acceptance",
    "provider_model_execution_rule": (
        "provider_model_acceptance_requires_dry_run_execution_request_and_ledgers"
    ),
    "production_evidence_rule": "search_quant_projection_contract_is_not_provider_model_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "candidate_is_not_buy_instruction": True,
}

COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT = {
    "schema_version": "command_center_daily_command_ordinary_workflow_contract.v1",
    "ordinary_entrance": "Daily Command Center",
    "preserved_capabilities": (
        "today_focus_pool",
        "risk_summary",
        "cache_status",
        "provider_health_summary",
        "missing_evidence_prompt",
        "last_successful_cache",
    ),
    "primary_next_click": "review_today_cache_or_missing_evidence",
    "summary_rule": "daily_command_center_shows_today_summary_before_engineering_detail",
    "source_state_rule": "daily_summary_shows_cache_provider_pending_or_degraded_state",
    "missing_evidence_rule": "daily_summary_missing_evidence_must_be_visible",
    "last_cache_rule": "last_successful_daily_cache_must_remain_visible",
    "research_boundary_rule": "daily_summary_is_research_only_no_buy_sell_instruction",
    "provider_health_rule": "provider_health_detail_moves_to_settings_config_health_or_audit",
    "legacy_freeze_rule": "legacy_home_rerun_buttons_and_engineering_tables_are_frozen",
    "not_migrated_legacy_paths": (
        "streamlit_multi_button_rerun_flow",
        "provider_health_auto_probe_on_home_render",
        "engineering_status_tables_before_decision_summary",
        "ai_text_as_operation_instruction",
        "unclear_next_step_home_layout",
    ),
    "required_visible_fields": (
        "today_focus_pool",
        "risk_summary",
        "source_state",
        "missing_evidence",
        "blocked_or_degraded_reason",
        "last_successful_cache/result",
        "next_click",
        "research_only_boundary",
        "task_boundary",
    ),
    "task_creation_rule": "daily_command_center_ordinary_workflow_never_creates_tasks_on_render",
    "cache_get_rule": "daily_command_center_get_cache_replays_latest_status_only",
    "production_evidence_rule": (
        "daily_command_center_ordinary_workflow_contract_is_not_provider_model_or_production_evidence"
    ),
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "daily_summary_is_not_buy_instruction": True,
}

COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT = {
    "schema_version": "command_center_stock_quant_projection_ordinary_workflow_contract.v1",
    "ordinary_entrance": "Stock Quant Projection",
    "preserved_capabilities": (
        "searched_symbol_single_stock_research",
        "factor_support_suppress_neutral_missing",
        "next_session_operation_zones",
        "optional_deepseek_explanation",
        "risk_budget_visibility",
    ),
    "primary_next_click": "生成 3.0 量化推演",
    "symbol_confirmation_rule": "confirmed_single_a_share_symbol_required_before_submit",
    "typing_rule": "search_typing_never_creates_task_or_provider_model_call",
    "task_route_rule": "work_creating_submit_uses_search_quant_projection_task_contract",
    "nonblocking_rule": "render_cache_then_show_task_status_and_last_successful_result",
    "source_state_rule": "projection_rows_show_cache_provider_model_pending_or_degraded_state",
    "missing_evidence_rule": "missing_provider_model_factor_next_echarts_or_browser_evidence_must_be_visible",
    "research_boundary_rule": "quant_projection_is_research_only_no_buy_sell_instruction",
    "legacy_freeze_rule": "legacy_sync_single_stock_room_and_ai_as_action_copy_are_frozen",
    "user_usable_entry_rule": (
        "stock_quant_projection_user_usable_entry_requires_confirmed_symbol_cache_task_status_and_research_boundary"
    ),
    "promotion_blocker_rule": (
        "stock_quant_projection_cannot_promote_from_search_typing_ai_text_or_local_receipt_only"
    ),
    "user_usable_required_evidence": (
        "confirmed_single_a_share_symbol_visible",
        "generate_3_0_quant_projection_button_or_disabled_reason_visible",
        "cache_result_or_last_successful_result_visible",
        "task_status_visible_after_submit",
        "provider_model_cache_pending_state_visible",
        "factor_next_echarts_or_browser_missing_evidence_visible",
        "deepseek_explanation_status_is_optional_and_explanation_only_visible",
        "research_only_no_buy_sell_or_strategy_action_boundary_visible",
    ),
    "forbidden_promotion_evidence": (
        "search_typing_only",
        "ai_text_as_action_only",
        "local_quant_projection_receipt_only",
        "provider_model_scope_ticket_only",
        "legacy_single_stock_room_ui_parity_only",
        "docs_config_scaffold_only",
    ),
    "not_migrated_legacy_paths": (
        "old_tab_radio_deep_navigation",
        "synchronous_blocking_projection",
        "conflicting_position_context",
        "deepseek_overwrites_numbers_or_strategy_action",
        "ai_text_as_trade_instruction",
    ),
    "required_visible_fields": (
        "confirmed_symbol",
        "next_click",
        "source_state",
        "missing_evidence",
        "last_successful_result",
        "task_status",
        "factor_support_suppress_neutral_missing",
        "next_session_operation_zones",
        "deepseek_state",
        "research_only_boundary",
    ),
    "task_creation_rule": "stock_quant_projection_ordinary_workflow_never_creates_tasks_on_typing_or_render",
    "cache_get_rule": "stock_quant_projection_get_cache_replays_latest_status_only",
    "production_evidence_rule": (
        "stock_quant_projection_ordinary_workflow_contract_is_not_provider_model_or_production_evidence"
    ),
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "projection_is_not_buy_instruction": True,
    "production_quant_projection_complete": False,
}

COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT = {
    "schema_version": "command_center_candidate_radar_ordinary_workflow_contract.v1",
    "ordinary_entrance": "Candidate Radar",
    "preserved_capabilities": (
        "Top/Watch/Excluded candidate groups",
        "scoring_reason",
        "scan_scope",
        "candidate_pool_source",
        "no_feature_loss_visibility",
    ),
    "primary_next_click": "review_last_radar_cache_or_button_gated_quick_scan",
    "quick_scan_rule": "quick_scan_must_be_button_gated_post_task_or_local_fallback",
    "last_cache_rule": "last_radar_cache_visible_before_scan_action",
    "coverage_gap_rule": "missing_full_pool_deep_scan_browser_ci_or_provider_evidence_must_be_visible",
    "source_state_rule": "candidate_rows_show_provider_cache_pending_or_degraded_state",
    "research_boundary_rule": "radar_candidate_is_not_buy_instruction",
    "legacy_freeze_rule": "legacy_fallback_recommendation_copy_is_frozen_until_replacement_evidence",
    "user_usable_entry_rule": "candidate_radar_user_usable_entry_requires_cache_scope_source_gap_and_no_buy_boundary",
    "promotion_blocker_rule": "candidate_radar_cannot_promote_from_legacy_ui_or_local_receipt_only",
    "user_usable_required_evidence": (
        "last_radar_cache_visible",
        "scan_scope_and_candidate_pool_source_visible",
        "top_watch_excluded_groups_visible",
        "scoring_reason_visible",
        "provider_cache_pending_or_degraded_state_visible",
        "missing_full_pool_deep_scan_browser_ci_or_provider_evidence_visible",
        "candidate_is_not_buy_instruction_visible",
        "quick_scan_button_or_disabled_reason_visible",
    ),
    "forbidden_promotion_evidence": (
        "old_streamlit_radar_ui_parity_only",
        "legacy_fallback_path_only",
        "no_feature_loss_matrix_only",
        "local_receipt_only",
        "stage_scope_manifest_only",
        "browser_artifact_without_provider_or_worker_evidence",
    ),
    "not_migrated_legacy_paths": (
        "recommendation_style_candidate_copy",
        "page_render_full_pool_scan",
        "page_render_deep_scan",
        "unclear_legacy_fallback_lineage",
        "performance_timeout_as_success",
    ),
    "required_visible_fields": (
        "candidate_group",
        "scoring_reason",
        "scan_scope",
        "candidate_pool_source",
        "source_state",
        "missing_evidence",
        "last_radar_cache",
        "task_status",
        "research_only_boundary",
    ),
    "task_creation_rule": "candidate_radar_ordinary_workflow_never_creates_tasks_on_render",
    "cache_get_rule": "candidate_radar_get_cache_replays_latest_status_only",
    "production_evidence_rule": (
        "candidate_radar_ordinary_workflow_contract_is_not_production_replacement_evidence"
    ),
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "candidate_is_not_buy_instruction": True,
    "production_radar_replacement_complete": False,
    "legacy_retirement_ready": False,
}

COMMAND_CENTER_ORDINARY_WORKFLOW_REGISTRY_CONTRACT = {
    "schema_version": "command_center_ordinary_workflow_registry_contract.v1",
    "ordinary_entrances": (
        {
            "entrance_key": "daily_command_center",
            "entrance_label": "Daily Command Center",
            "workflow_contract": "COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT",
            "read_function": "get_command_center_daily_command_ordinary_workflow_contract()",
            "primary_next_click": "review_today_cache_or_missing_evidence",
            "work_creation_surface": "none_from_render",
        },
        {
            "entrance_key": "stock_quant_projection",
            "entrance_label": "Stock Quant Projection",
            "workflow_contract": "COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT",
            "read_function": "get_command_center_stock_quant_projection_ordinary_workflow_contract()",
            "primary_next_click": "生成 3.0 量化推演",
            "work_creation_surface": "confirmed_symbol_submit_post_task_or_local_fallback",
        },
        {
            "entrance_key": "candidate_radar",
            "entrance_label": "Candidate Radar",
            "workflow_contract": "COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT",
            "read_function": "get_command_center_candidate_radar_ordinary_workflow_contract()",
            "primary_next_click": "review_last_radar_cache_or_button_gated_quick_scan",
            "work_creation_surface": "button_gated_quick_scan_post_task_or_local_fallback",
        },
    ),
    "registry_rule": "three_ordinary_entrances_are_the_primary_user_workflow",
    "placement_rule": "ordinary_registry_rows_appear_before_settings_developer_audit",
    "shared_summary_rule": (
        "each_registered_entrance_shows_next_click_source_state_missing_evidence_"
        "research_boundary_blocked_degraded_and_last_successful_result"
    ),
    "task_creation_rule": "ordinary_workflow_registry_never_creates_tasks",
    "cache_write_rule": "ordinary_workflow_registry_never_writes_cache_or_config",
    "production_evidence_rule": "ordinary_workflow_registry_contract_is_not_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT = {
    "schema_version": "command_center_ordinary_source_state_display_contract.v1",
    "ordinary_entrances": (
        {
            "entrance_key": "daily_command_center",
            "entrance_label": "Daily Command Center",
            "display_fields": (
                "cache_status",
                "provider_health_summary",
                "deepseek_explanation_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_successful_cache/result",
            ),
        },
        {
            "entrance_key": "stock_quant_projection",
            "entrance_label": "Stock Quant Projection",
            "display_fields": (
                "cache_result_state",
                "tushare_provider_state",
                "factor_state",
                "next_session_state",
                "deepseek_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_successful_result",
            ),
        },
        {
            "entrance_key": "candidate_radar",
            "entrance_label": "Candidate Radar",
            "display_fields": (
                "candidate_cache_state",
                "provider_parity_state",
                "scan_scope_state",
                "deepseek_deep_scan_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_radar_cache",
            ),
        },
    ),
    "shared_state_rule": "provider_model_cache_pending_states_must_be_visible_in_ordinary_summary",
    "provider_rule": "tushare_state_requires_call_ledger_or_provider_pending_marker",
    "model_rule": "deepseek_state_is_explanation_only_with_model_ledger_or_pending_marker",
    "cache_rule": "cache_state_must_show_freshness_and_last_successful_pointer",
    "pending_rule": "pending_state_must_name_missing_evidence_or_next_allowed_task",
    "degraded_rule": "degraded_state_must_show_blocker_and_safe_fallback",
    "non_action_rule": "source_state_display_is_not_next_click_or_trade_action",
    "page_visibility_rule": (
        "ordinary_source_state_page_visibility_requires_provider_model_cache_pending_last_successful_and_blocker_rows"
    ),
    "promotion_blocker_rule": (
        "ordinary_source_state_cannot_promote_from_hidden_tabs_tooltips_or_engineering_tables_only"
    ),
    "page_visibility_required_evidence": (
        "source_state_visible_in_ordinary_summary",
        "cache_freshness_and_last_successful_pointer_visible",
        "tushare_call_ledger_or_provider_pending_marker_visible",
        "deepseek_model_ledger_or_pending_marker_visible",
        "pending_missing_evidence_or_next_allowed_task_visible",
        "degraded_blocker_and_safe_fallback_visible",
        "no_trade_no_action_boundary_visible_next_to_state",
        "settings_developer_audit_link_for_detail_visible",
    ),
    "forbidden_page_visibility_evidence": (
        "engineering_audit_table_only",
        "settings_detail_only",
        "tooltip_only",
        "hidden_tab_only",
        "local_receipt_only",
        "docs_config_scaffold_only",
    ),
    "task_creation_rule": "ordinary_source_state_display_never_creates_tasks",
    "cache_write_rule": "ordinary_source_state_display_never_writes_cache_or_config",
    "production_evidence_rule": (
        "ordinary_source_state_display_contract_is_not_provider_model_or_production_evidence"
    ),
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_ORDINARY_SOURCE_STATE_VOCABULARY = (
    "cache",
    "Tushare",
    "DeepSeek",
    "pending",
    "degraded",
    "last_successful_cache/result",
)

COMMAND_CENTER_ORDINARY_SOURCE_STATE_CONTRACT = {
    "schema_version": "command_center_ordinary_source_state_contract.v1",
    "ordinary_entrances": (
        "Daily Command Center",
        "Stock Quant Projection",
        "Candidate Radar",
    ),
    "vocabulary": COMMAND_CENTER_ORDINARY_SOURCE_STATE_VOCABULARY,
    "cache": "visible_value_from_local_packet_or_cache",
    "Tushare": "provider_backed_or_provider_pending_market_data_with_call_ledger_status",
    "DeepSeek": "explanation_only_model_output_never_data_source_or_action_writer",
    "pending": "missing_not_run_or_waiting_evidence",
    "degraded": "stale_failed_or_partial_source_with_visible_blocker",
    "last_successful_cache/result": "latest_safe_fallback_result",
    "ui_rule": "read_only_source_state_chips_in_ordinary_summary",
    "missing_evidence_rule": "pending_or_degraded_state_must_show_missing_evidence_or_blocker",
    "deepseek_boundary": "deepseek_never_overwrites_price_holding_factor_operation_zone_or_strategy_action",
    "task_creation_rule": "source_state_chips_never_create_tasks",
    "cache_write_rule": "source_state_chips_never_write_cache_or_config",
    "production_evidence_rule": "source_state_contract_is_not_provider_model_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT = {
    "schema_version": "command_center_ordinary_next_click_contract.v1",
    "ordinary_entrances": (
        {
            "entrance_key": "daily_command_center",
            "entrance_label": "Daily Command Center",
            "primary_next_click": "review_today_cache_or_missing_evidence",
            "work_creating": False,
        },
        {
            "entrance_key": "stock_quant_projection",
            "entrance_label": "Stock Quant Projection",
            "primary_next_click": "生成 3.0 量化推演",
            "work_creating": True,
            "task_contract": "COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT",
        },
        {
            "entrance_key": "candidate_radar",
            "entrance_label": "Candidate Radar",
            "primary_next_click": "review_last_radar_cache_or_button_gated_quick_scan",
            "work_creating": "button_gated_when_quick_scan_selected",
        },
    ),
    "one_primary_action_rule": "one_primary_safe_action_per_ordinary_entrance",
    "blocked_reason_rule": "disabled_or_degraded_reason_visible_before_click",
    "non_action_surfaces": (
        "search_typing",
        "react_render",
        "mode_banner",
        "source_state_chip",
        "deepseek_text",
        "radar_candidate",
    ),
    "work_creation_rule": "work_creating_next_click_must_use_post_task_worker_or_local_fallback",
    "task_status_rule": "work_creating_next_click_must_show_task_status",
    "research_boundary_rule": "next_click_is_research_only_no_buy_sell_instruction",
    "production_evidence_rule": "ordinary_next_click_contract_is_not_execution_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "radar_candidate_is_buy_instruction": False,
}

COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT = {
    "schema_version": "command_center_ordinary_research_boundary_contract.v1",
    "ordinary_entrances": (
        "Daily Command Center",
        "Stock Quant Projection",
        "Candidate Radar",
    ),
    "boundary_label": "research_only_not_buy_sell_instruction",
    "ui_rule": "show_research_only_boundary_in_ordinary_summary",
    "deepseek_rule": "deepseek_text_is_explanation_only_not_data_source_or_action",
    "factor_rule": "factor_scores_are_research_evidence_not_trade_action",
    "radar_rule": "radar_candidate_is_not_buy_instruction",
    "next_session_rule": "operation_zones_are_conditions_not_orders",
    "task_receipt_rule": "task_receipts_are_evidence_not_trade_instruction",
    "forbidden_interpretations": (
        "buy_signal",
        "sell_signal",
        "position_order",
        "broker_order",
        "strategy_action_mutation",
        "deepseek_as_data_source",
    ),
    "mutation_rule": "never_modify_strategy_action_prices_positions_factors_or_operation_zones",
    "production_evidence_rule": "research_boundary_contract_is_not_execution_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "radar_candidate_is_buy_instruction": False,
    "deepseek_text_is_buy_instruction": False,
    "factor_score_is_buy_instruction": False,
}

COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT = {
    "schema_version": "command_center_ordinary_evidence_fallback_contract.v1",
    "ordinary_entrances": (
        "Daily Command Center",
        "Stock Quant Projection",
        "Candidate Radar",
    ),
    "missing_evidence_rule": "missing_evidence_must_be_visible_before_action",
    "blocked_state_rule": "blocked_state_must_show_blocker_and_allowed_next_step",
    "degraded_state_rule": "degraded_state_must_show_stale_failed_or_partial_source",
    "last_successful_rule": "last_successful_cache_or_result_must_remain_visible_as_fallback",
    "fallback_boundary_rule": "fallback_is_display_only_not_current_provider_model_evidence",
    "required_visible_fields": (
        "missing_evidence",
        "blocked_reason",
        "degraded_reason",
        "last_successful_cache/result",
        "freshness_state",
        "task_status",
    ),
    "non_evidence_states": (
        "pending",
        "degraded",
        "stale",
        "failed",
        "partial",
        "last_successful_cache/result",
    ),
    "task_creation_rule": "evidence_fallback_display_never_creates_tasks",
    "cache_write_rule": "evidence_fallback_display_never_writes_cache_or_config",
    "production_evidence_rule": "evidence_fallback_contract_is_not_provider_model_or_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT = {
    "schema_version": "command_center_legacy_audit_classification_contract.v1",
    "classifications": (
        "KEEP",
        "REDESIGN",
        "LEGACY-DEBUG",
        "RETIRE",
    ),
    "ordinary_workflow_scope": (
        "home/daily command",
        "searched-symbol quant projection",
        "candidate radar",
        "next-session map",
        "factor/risk/provider health",
        "discipline/backtest",
        "ETF/leverage",
        "external brain/AI advisor",
    ),
    "keep_promotion_rule": "keep_requires_direct_legacy_bug_ux_audit_evidence",
    "redesign_rule": "useful_capability_rebuild_old_ux_or_code_before_ordinary_flow",
    "legacy_debug_rule": "admin_debug_fallback_only_not_ordinary_flow",
    "retire_rule": "freeze_or_remove_from_ordinary_user_workflow",
    "seed_only_rule": "seed_inventory_receipt_matrix_or_docs_config_cannot_promote_keep",
    "direct_evidence_rule": "direct_evidence_row_required_before_keep_or_ordinary_entry",
    "seed_status_rule": "seed_only_rows_default_to_redesign_legacy_debug_or_retire",
    "lineage_rule": "unclear_data_lineage_blocks_ordinary_entry_until_redesigned_or_frozen",
    "scope_rule": "audit_scope_tracks_workflow_group_not_legacy_file_or_tab_count",
    "ordinary_entry_rule": "ordinary_entry_requires_replacement_entrance_and_frozen_legacy_path",
    "keep_entry_rule": "keep_requires_direct_evidence_and_no_open_bug_or_lineage_blocker",
    "redesign_entry_rule": "redesign_requires_replacement_workflow_before_ordinary_entry",
    "transition_rules": (
        "seed_only_cannot_transition_to_keep",
        "direct_evidence_ready_can_transition_to_keep_only_with_all_required_fields",
        "blocked_by_lineage_transitions_to_redesign_legacy_debug_or_retire",
        "known_bug_or_patchwork_without_replacement_stays_redesign_or_retire",
        "legacy_debug_and_retire_do_not_enter_ordinary_user_flow",
    ),
    "ordinary_entry_allowed_after_audit": (
        "KEEP",
        "REDESIGN_WITH_REPLACEMENT_READY",
    ),
    "ordinary_entry_forbidden_after_audit": (
        "LEGACY-DEBUG",
        "RETIRE",
        "seed_only",
        "blocked_by_lineage",
        "REDESIGN_WITHOUT_REPLACEMENT_READY",
    ),
    "streamlit_fallback_rule": "streamlit_remains_fallback_admin_debug_until_react_tauri_workflow_is_easier_clearer_more_reliable",
    "streamlit_primary_surface_rule": "streamlit_must_not_be_primary_3_0_runtime_or_target_ux",
    "fallback_retirement_rule": "fallback_retirement_requires_replacement_workflow_direct_evidence_and_rollback_plan",
    "fallback_retirement_required_evidence": (
        "react_tauri_replacement_workflow_ready",
        "ordinary_entry_easier_clearer_more_reliable_evidence",
        "direct_legacy_bug_ux_audit_complete",
        "provider_model_cache_pending_state_visible",
        "last_successful_cache_or_result_visible",
        "rollback_or_admin_debug_path_retained_until_promotion",
    ),
    "fallback_retirement_forbidden_evidence": (
        "streamlit_ui_polish_only",
        "route_inventory_only",
        "local_receipt_only",
        "stage_scope_manifest_only",
        "no_feature_loss_matrix_only",
        "docs_config_scaffold_only",
    ),
    "evidence_statuses": (
        "seed_only",
        "direct_evidence_pending",
        "direct_evidence_ready",
        "blocked_by_lineage",
        "frozen_or_retired",
    ),
    "forbidden_keep_evidence_sources": (
        "route_inventory_only",
        "legacy_tab_name_only",
        "docs_config_scaffold_only",
        "local_receipt_only",
        "no_feature_loss_matrix_only",
        "mock_sanitizer_or_preflight_only",
    ),
    "required_evidence_fields": (
        "observed_user_action_or_workflow_problem",
        "legacy_bug_confusing_ux_or_patchwork_removed",
        "data_lineage_check",
        "replacement_ordinary_entrance",
        "frozen_legacy_path",
    ),
    "row_evidence_rule": (
        "legacy_audit_row_requires_scope_status_direct_source_lineage_replacement_and_freeze_decision"
    ),
    "row_required_fields": (
        "workflow_group",
        "legacy_surface_or_module",
        "observed_user_action_or_workflow_problem",
        "direct_ux_bug_evidence_source",
        "classification",
        "evidence_status",
        "data_lineage_check",
        "replacement_ordinary_entrance",
        "frozen_legacy_path",
        "ordinary_entry_decision",
        "next_action",
    ),
    "forbidden_row_completion_evidence": (
        "file_inventory_only",
        "legacy_tab_count_only",
        "route_exists_only",
        "local_receipt_only",
        "docs_config_scaffold_only",
        "no_feature_loss_matrix_only",
    ),
    "seed_rows_rule": "legacy_audit_seed_rows_cover_ordinary_workflow_scope_without_keep_promotion",
    "seed_row_promotion_rule": "legacy_audit_seed_rows_are_not_direct_evidence_or_production_evidence",
    "seed_rows": (
        {
            "workflow_group": "home/daily command",
            "legacy_surface_or_module": "streamlit_home_daily_summary",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_home_rerun_buttons_and_unclear_next_step"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "REDESIGN",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_cache_provider_lineage_review",
            "replacement_ordinary_entrance": "Daily Command Center",
            "frozen_legacy_path": "legacy_streamlit_home_rerun_flow_frozen",
            "ordinary_entry_decision": "not_promoted_seed_only",
            "next_action": "capture_direct_ux_bug_evidence_and_cache_lineage_before_keep",
        },
        {
            "workflow_group": "searched-symbol quant projection",
            "legacy_surface_or_module": "legacy_single_stock_room_quant_projection",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_deep_navigation_blocking_projection_ai_as_action"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "REDESIGN",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_factor_next_deepseek_lineage_review",
            "replacement_ordinary_entrance": "Stock Quant Projection",
            "frozen_legacy_path": "legacy_sync_single_stock_room_ai_as_action_frozen",
            "ordinary_entry_decision": "not_promoted_seed_only",
            "next_action": "capture_direct_ux_bug_evidence_and_projection_lineage_before_keep",
        },
        {
            "workflow_group": "candidate radar",
            "legacy_surface_or_module": "legacy_candidate_radar",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_fallback_recommendation_copy_full_pool_deep_scan_boundary"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "REDESIGN",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_candidate_pool_and_scoring_lineage_review",
            "replacement_ordinary_entrance": "Candidate Radar",
            "frozen_legacy_path": "legacy_fallback_radar_recommendation_copy_frozen",
            "ordinary_entry_decision": "not_promoted_seed_only",
            "next_action": "capture_direct_ux_bug_evidence_and_radar_lineage_before_keep",
        },
        {
            "workflow_group": "next-session map",
            "legacy_surface_or_module": "legacy_next_session_chart",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_chart_ui_receipt_as_replacement_and_browser_perf"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "REDESIGN",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_operation_zone_and_echarts_lineage_review",
            "replacement_ordinary_entrance": "Stock Quant Projection",
            "frozen_legacy_path": "legacy_streamlit_chart_ui_receipt_as_replacement_frozen",
            "ordinary_entry_decision": "not_promoted_seed_only",
            "next_action": "capture_direct_chart_ux_and_browser_lineage_evidence_before_keep",
        },
        {
            "workflow_group": "factor/risk/provider health",
            "legacy_surface_or_module": "legacy_factor_risk_provider_health_tables",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_engineering_tables_risk_gap_and_provider_health_dominance"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "REDESIGN",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_factor_risk_provider_lineage_review",
            "replacement_ordinary_entrance": "Daily Command Center / Stock Quant Projection / Settings Config Health",
            "frozen_legacy_path": "legacy_engineering_tables_and_provider_health_as_ordinary_flow_frozen",
            "ordinary_entry_decision": "not_promoted_seed_only",
            "next_action": "split_factor_risk_provider_rows_with_direct_ux_bug_evidence",
        },
        {
            "workflow_group": "discipline/backtest",
            "legacy_surface_or_module": "legacy_discipline_backtest_lab",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_deep_forms_sync_backtest_and_trade_advice_mixing"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "LEGACY-DEBUG",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_backtest_history_lineage_review",
            "replacement_ordinary_entrance": "Settings / Developer / Audit",
            "frozen_legacy_path": "legacy_sync_backtest_forms_as_ordinary_advice_frozen",
            "ordinary_entry_decision": "not_promoted_legacy_debug",
            "next_action": "redesign_as_clear_backtest_lab_before_ordinary_entry",
        },
        {
            "workflow_group": "ETF/leverage",
            "legacy_surface_or_module": "legacy_margin_etf_leverage_flow",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_leverage_budget_mixed_with_ordinary_action"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "LEGACY-DEBUG",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_leverage_risk_budget_lineage_review",
            "replacement_ordinary_entrance": "future_risk_budget_subflow_pending",
            "frozen_legacy_path": "legacy_leverage_advice_and_complex_manual_refresh_frozen",
            "ordinary_entry_decision": "not_promoted_legacy_debug",
            "next_action": "redesign_as_risk_budget_subflow_before_ordinary_entry",
        },
        {
            "workflow_group": "external brain/AI advisor",
            "legacy_surface_or_module": "legacy_external_brain_ai_advisor",
            "observed_user_action_or_workflow_problem": (
                "direct_evidence_pending_rag_probe_and_ai_trade_advice_lineage_confusion"
            ),
            "direct_ux_bug_evidence_source": "direct_ux_bug_evidence_pending",
            "classification": "RETIRE",
            "evidence_status": "seed_only",
            "data_lineage_check": "pending_external_memory_and_model_lineage_reset",
            "replacement_ordinary_entrance": "governed_deepseek_explanation_only_if_rebuilt",
            "frozen_legacy_path": "legacy_ai_trade_advice_and_external_probe_ordinary_path_frozen",
            "ordinary_entry_decision": "not_promoted_retire",
            "next_action": "retire_trade_advice_and_rebuild_only_as_explanation_with_lineage",
        },
    ),
    "production_evidence_rule": "legacy_audit_classification_contract_is_not_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT = {
    "schema_version": "command_center_migration_checkpoint_contract.v1",
    "required_questions": (
        "what_user_capability_was_preserved",
        "what_legacy_ux_problem_was_removed",
        "what_legacy_bug_or_patchwork_path_was_not_migrated",
        "what_became_simpler_for_nontechnical_user",
        "which_real_blocker_was_reduced",
    ),
    "checkpoint_rule": "every_future_migration_checkpoint_must_answer_five_questions",
    "keep_gate_rule": "cannot_promote_keep_or_ordinary_flow_without_checkpoint_answers",
    "release_blocker_rule": "broad_contract_receipt_runbook_or_manifest_requires_named_release_blocker",
    "scope_rule": "checkpoint_answers_must_reference_the_touched_user_workflow_or_release_blocker",
    "non_evidence_rule": "checkpoint_answers_are_planning_evidence_not_production_acceptance",
    "priority_order": (
        "fix_push_gate_ci_evidence",
        "legacy_bug_ux_audit_for_streamlit_ordinary_workflows",
        "rebuild_ltg13_candidate_radar_user_usable_workflow",
        "searched_symbol_to_generate_3_0_quant_projection",
        "show_provider_model_cache_pending_state_on_page",
        "move_engineering_audit_tables_out_of_ordinary_flow",
    ),
    "priority_rule": "future_migration_slices_follow_current_priority_order_or_name_blocker_exception",
    "ci_rule": "remote_ci_unverified_remains_release_blocker_until_current_green_or_reviewed_logs",
    "ci_required_evidence": (
        "matching_head_sha_or_commit",
        "current_remote_actions_green_or_failed_step_reviewed",
        "fresh_local_push_gate_result_for_current_head",
        "safe_failure_log_excerpt_or_green_run_url",
        "explicit_user_push_confirmation_before_push",
    ),
    "ci_non_evidence_sources": (
        "local_unit_tests_only",
        "checkpoint_answer_only",
        "static_workflow_file_presence_only",
        "ci_failure_email_without_matching_run_logs",
        "old_remote_green_run_for_different_head",
        "local_receipt_or_stage_scope_manifest_only",
    ),
    "ci_review_row_rule": "remote_ci_review_row_requires_head_status_log_local_gate_push_decision",
    "ci_review_required_fields": (
        "head_sha_or_commit",
        "remote_run_url_or_id",
        "remote_status",
        "failed_step_or_green_status",
        "safe_failure_log_excerpt_or_green_run_url",
        "local_gate_result_for_same_head",
        "push_confirmation_state",
        "release_claim_decision",
        "next_action",
    ),
    "ci_review_forbidden_completion_evidence": (
        "old_run_without_matching_head",
        "email_subject_only",
        "local_gate_pass_only",
        "workflow_yaml_presence_only",
        "unreviewed_failed_step",
        "unchecked_artifact_or_secret_scan",
    ),
    "ci_review_seed_row_rule": "remote_ci_review_seed_row_keeps_p0_blocked_until_matching_remote_run_review",
    "ci_review_seed_row": {
        "head_sha_or_commit": "pending_current_head_sha",
        "remote_run_url_or_id": "pending_remote_actions_run",
        "remote_status": "remote_ci_unverified",
        "failed_step_or_green_status": "not_reviewed",
        "safe_failure_log_excerpt_or_green_run_url": "pending_safe_log_excerpt_or_green_run_url",
        "local_gate_result_for_same_head": "pending_fresh_local_push_gate_for_current_head",
        "push_confirmation_state": "not_requested_no_push",
        "release_claim_decision": "blocked_remote_ci_unverified",
        "next_action": "review_matching_remote_actions_run_or_attach_safe_failed_step_logs_after_local_gate",
    },
    "release_claim_rule": "release_or_production_replacement_claim_requires_current_remote_ci_green_or_reviewed_failure_logs",
    "push_rule": "push_requires_explicit_user_confirmation_after_local_gate_review",
    "github_api_rule": "ci_checkpoint_contract_never_calls_github_or_fetches_actions_logs",
    "legacy_audit_rule": "legacy_bug_ux_audit_precedes_major_ordinary_workflow_migration",
    "ordinary_flow_rule": "ordinary_user_workflow_slices_precede_extra_engineering_scaffold",
    "forbidden_shortcuts": (
        "claiming_ltg_complete_from_docs_config_scaffold",
        "using_receipt_matrix_or_sanitizer_as_production_evidence",
        "copying_legacy_ui_without_ux_bug_audit",
        "omitting_blocker_reduction",
        "starting_new_broad_ltg_surface_without_named_current_release_blocker",
        "treating_local_gate_or_checkpoint_as_remote_ci_green",
    ),
    "task_creation_rule": "migration_checkpoint_contract_never_creates_tasks",
    "cache_write_rule": "migration_checkpoint_contract_never_writes_cache_or_config",
    "production_evidence_rule": "migration_checkpoint_contract_is_not_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "worker_dispatch_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}

COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT = {
    "schema_version": "command_center_ordinary_audit_placement_contract.v1",
    "ordinary_entrances": (
        "Daily Command Center",
        "Stock Quant Projection",
        "Candidate Radar",
    ),
    "ordinary_summary_allowed_fields": (
        "next_click",
        "source_state",
        "missing_evidence",
        "research_only_boundary",
        "blocked_or_degraded_reason",
        "last_successful_cache/result",
        "task_boundary",
    ),
    "audit_detail_surfaces": (
        "Settings",
        "Developer",
        "Audit",
    ),
    "demoted_detail_types": (
        "engineering_contract_tables",
        "receipt_rows",
        "runbooks",
        "LTG_audit_surfaces",
        "lineage_details",
    ),
    "ordinary_promotion_required_evidence": (
        "next_click_visible_before_audit_detail",
        "source_state_visible_before_audit_detail",
        "missing_evidence_visible_before_audit_detail",
        "research_only_boundary_visible_before_audit_detail",
        "blocked_or_degraded_reason_visible_before_audit_detail",
        "last_successful_cache_or_result_visible_before_audit_detail",
        "task_boundary_visible_before_audit_detail",
        "settings_developer_audit_link_visible_for_details",
    ),
    "ordinary_first_view_forbidden_surfaces": (
        "engineering_contract_table_as_primary_surface",
        "receipt_rows_as_primary_surface",
        "runbook_as_primary_surface",
        "ltg_audit_table_as_primary_surface",
        "legacy_route_inventory_as_primary_surface",
    ),
    "placement_rule": "ordinary_pages_show_user_summary_before_engineering_audit_details",
    "promotion_rule": "ordinary_entry_promotion_requires_user_summary_fields_before_engineering_detail",
    "demotion_rule": "detailed_engineering_audit_tables_move_to_settings_developer_audit",
    "first_view_rule": "ordinary_first_view_shows_next_click_state_gaps_boundary_and_last_success_before_audit",
    "exception_rule": "ordinary_pages_include_engineering_detail_only_for_current_decision_surface",
    "dominance_rule": "engineering_contract_tables_must_not_dominate_ordinary_pages",
    "audit_demotion_rule": "ordinary_first_view_must_not_be_engineering_audit_dashboard",
    "audit_demotion_required_evidence": (
        "ordinary_summary_rendered_before_any_engineering_table",
        "engineering_contract_tables_demoted_to_settings_developer_audit",
        "receipt_rows_demoted_to_settings_developer_audit",
        "runbooks_demoted_to_settings_developer_audit",
        "ltg_audit_surfaces_demoted_to_settings_developer_audit",
        "current_decision_surface_exception_reason_visible_when_detail_stays",
        "settings_developer_audit_link_visible_after_summary",
    ),
    "forbidden_audit_demotion_evidence": (
        "audit_table_before_user_summary",
        "receipt_rows_before_next_click",
        "runbook_before_source_state",
        "ltg_audit_as_default_page_body",
        "all_details_hidden_without_audit_link",
        "local_receipt_only",
        "docs_config_scaffold_only",
    ),
    "task_creation_rule": "audit_placement_display_never_creates_tasks",
    "cache_write_rule": "audit_placement_display_never_writes_cache_or_config",
    "production_evidence_rule": "ordinary_audit_placement_contract_is_not_production_evidence",
    "external_calls_triggered": False,
    "provider_execution_implemented": False,
    "model_execution_implemented": False,
    "contains_secret": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
}


CONFIG_NAMES = {
    *COMMAND_CENTER_RUNTIME_CONFIG_NAMES,
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_AUTO_EXPLAIN_ENABLED",
    "DEEPSEEK_DEFAULT_MODEL",
    "DEEPSEEK_EXPLAIN_MODEL",
    "DEEPSEEK_FACTOR_EXPLAIN_MODE",
    "DEEPSEEK_FAST_MODEL",
    "DEEPSEEK_TOKEN_1",
    "DEEPSEEK_TOKEN_2",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
    "TUSHARE_TOKEN",
}

DEEPSEEK_FACTOR_EXPLAIN_MODES = {"manual_only", "auto_after_task", "disabled"}

DEEPSEEK_MODEL_DEFAULTS = {
    "default": "deepseek-v4-pro",
    "explain": "deepseek-v4-pro",
    "projection": "deepseek-v4-pro",
    "factor_explain": "deepseek-v4-pro",
    "fast": "deepseek-v4-flash",
    "healthcheck": "deepseek-v4-flash",
    "feeder": "deepseek-v4-flash",
}

DEEPSEEK_MODEL_CONFIG_KEYS = {
    "default": ("DEEPSEEK_DEFAULT_MODEL",),
    "explain": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "projection": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "factor_explain": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "fast": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "healthcheck": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "feeder": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
}


def get_command_center_runtime_mode_policies():
    """Return safe runtime-mode policy rows for docs, status packets, and tests."""

    return [dict(row) for row in COMMAND_CENTER_RUNTIME_MODE_POLICIES]


def get_command_center_runtime_mode_config_contract():
    """Return the safe read/display contract for COMMAND_CENTER_BOOTSTRAP_MODE."""

    contract = dict(COMMAND_CENTER_RUNTIME_MODE_CONFIG_CONTRACT)
    contract["allowed_modes"] = list(COMMAND_CENTER_RUNTIME_MODES)
    contract["policy_row_count"] = len(COMMAND_CENTER_RUNTIME_MODE_POLICIES)
    return contract


def get_command_center_live_light_bootstrap_task_contract():
    """Return the config-owned contract for the bounded live_light startup task."""

    contract = dict(COMMAND_CENTER_LIVE_LIGHT_BOOTSTRAP_TASK_CONTRACT)
    contract["source_switch_config_keys"] = list(
        COMMAND_CENTER_LIVE_LIGHT_BOOTSTRAP_TASK_CONTRACT["source_switch_config_keys"]
    )
    contract["allowed_external_execution_profiles"] = list(COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES)
    contract["default_external_execution_profile"] = COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
    contract["allowed_research_scopes"] = list(COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES)
    contract["default_research_scope"] = COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
    return contract


def get_command_center_search_quant_projection_task_contract():
    """Return the config-owned contract for searched-symbol quant projection submit."""

    return dict(COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT)


def get_command_center_daily_command_ordinary_workflow_contract():
    """Return the config-owned ordinary workflow contract for Daily Command Center."""

    contract = dict(COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT)
    contract["preserved_capabilities"] = list(
        COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT["preserved_capabilities"]
    )
    contract["not_migrated_legacy_paths"] = list(
        COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT["not_migrated_legacy_paths"]
    )
    contract["required_visible_fields"] = list(
        COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT["required_visible_fields"]
    )
    return contract


def get_command_center_stock_quant_projection_ordinary_workflow_contract():
    """Return the config-owned ordinary workflow contract for Stock Quant Projection."""

    contract = dict(COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT)
    contract["preserved_capabilities"] = list(
        COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT["preserved_capabilities"]
    )
    contract["not_migrated_legacy_paths"] = list(
        COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT["not_migrated_legacy_paths"]
    )
    contract["user_usable_required_evidence"] = list(
        COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT["user_usable_required_evidence"]
    )
    contract["forbidden_promotion_evidence"] = list(
        COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT["forbidden_promotion_evidence"]
    )
    contract["required_visible_fields"] = list(
        COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT["required_visible_fields"]
    )
    return contract


def get_command_center_candidate_radar_ordinary_workflow_contract():
    """Return the config-owned ordinary workflow contract for Candidate Radar."""

    contract = dict(COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT)
    contract["preserved_capabilities"] = list(
        COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT["preserved_capabilities"]
    )
    contract["not_migrated_legacy_paths"] = list(
        COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT["not_migrated_legacy_paths"]
    )
    contract["user_usable_required_evidence"] = list(
        COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT["user_usable_required_evidence"]
    )
    contract["forbidden_promotion_evidence"] = list(
        COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT["forbidden_promotion_evidence"]
    )
    contract["required_visible_fields"] = list(
        COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT["required_visible_fields"]
    )
    return contract


def get_command_center_ordinary_workflow_registry_contract():
    """Return the config-owned registry for the three ordinary entrances."""

    contract = dict(COMMAND_CENTER_ORDINARY_WORKFLOW_REGISTRY_CONTRACT)
    contract["ordinary_entrances"] = [
        dict(row) for row in COMMAND_CENTER_ORDINARY_WORKFLOW_REGISTRY_CONTRACT["ordinary_entrances"]
    ]
    return contract


def get_command_center_ordinary_source_state_display_contract():
    """Return the config-owned source-state display fields for ordinary entrances."""

    contract = dict(COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT)
    contract["ordinary_entrances"] = []
    for row in COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT["ordinary_entrances"]:
        copied = dict(row)
        copied["display_fields"] = list(row["display_fields"])
        contract["ordinary_entrances"].append(copied)
    contract["page_visibility_required_evidence"] = list(
        COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT["page_visibility_required_evidence"]
    )
    contract["forbidden_page_visibility_evidence"] = list(
        COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT["forbidden_page_visibility_evidence"]
    )
    return contract


def get_command_center_ordinary_source_state_contract():
    """Return the config-owned source-state vocabulary for ordinary entrances."""

    contract = dict(COMMAND_CENTER_ORDINARY_SOURCE_STATE_CONTRACT)
    contract["ordinary_entrances"] = list(COMMAND_CENTER_ORDINARY_SOURCE_STATE_CONTRACT["ordinary_entrances"])
    contract["vocabulary"] = list(COMMAND_CENTER_ORDINARY_SOURCE_STATE_VOCABULARY)
    return contract


def get_command_center_ordinary_next_click_contract():
    """Return the config-owned next-click contract for ordinary entrances."""

    contract = dict(COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT)
    contract["ordinary_entrances"] = [
        dict(row) for row in COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT["ordinary_entrances"]
    ]
    contract["non_action_surfaces"] = list(COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT["non_action_surfaces"])
    return contract


def get_command_center_ordinary_research_boundary_contract():
    """Return the config-owned research-only boundary for ordinary entrances."""

    contract = dict(COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT)
    contract["ordinary_entrances"] = list(
        COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT["ordinary_entrances"]
    )
    contract["forbidden_interpretations"] = list(
        COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT["forbidden_interpretations"]
    )
    return contract


def get_command_center_ordinary_evidence_fallback_contract():
    """Return the config-owned missing-evidence and fallback contract."""

    contract = dict(COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT)
    contract["ordinary_entrances"] = list(
        COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT["ordinary_entrances"]
    )
    contract["required_visible_fields"] = list(
        COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT["required_visible_fields"]
    )
    contract["non_evidence_states"] = list(
        COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT["non_evidence_states"]
    )
    return contract


def get_command_center_legacy_audit_classification_contract():
    """Return the config-owned Legacy Bug / UX Audit classification gate."""

    contract = dict(COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT)
    contract["classifications"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["classifications"]
    )
    contract["ordinary_workflow_scope"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["ordinary_workflow_scope"]
    )
    contract["evidence_statuses"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["evidence_statuses"]
    )
    contract["forbidden_keep_evidence_sources"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["forbidden_keep_evidence_sources"]
    )
    contract["transition_rules"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["transition_rules"]
    )
    contract["ordinary_entry_allowed_after_audit"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["ordinary_entry_allowed_after_audit"]
    )
    contract["ordinary_entry_forbidden_after_audit"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["ordinary_entry_forbidden_after_audit"]
    )
    contract["fallback_retirement_required_evidence"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["fallback_retirement_required_evidence"]
    )
    contract["fallback_retirement_forbidden_evidence"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["fallback_retirement_forbidden_evidence"]
    )
    contract["required_evidence_fields"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["required_evidence_fields"]
    )
    contract["row_required_fields"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["row_required_fields"]
    )
    contract["forbidden_row_completion_evidence"] = list(
        COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["forbidden_row_completion_evidence"]
    )
    contract["seed_rows"] = [
        dict(row) for row in COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT["seed_rows"]
    ]
    return contract


def get_command_center_migration_checkpoint_contract():
    """Return the config-owned migration checkpoint question gate."""

    contract = dict(COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT)
    contract["required_questions"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["required_questions"]
    )
    contract["priority_order"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["priority_order"]
    )
    contract["ci_required_evidence"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["ci_required_evidence"]
    )
    contract["ci_non_evidence_sources"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["ci_non_evidence_sources"]
    )
    contract["ci_review_required_fields"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["ci_review_required_fields"]
    )
    contract["ci_review_forbidden_completion_evidence"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["ci_review_forbidden_completion_evidence"]
    )
    contract["ci_review_seed_row"] = dict(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["ci_review_seed_row"]
    )
    contract["forbidden_shortcuts"] = list(
        COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT["forbidden_shortcuts"]
    )
    return contract


def get_command_center_ordinary_audit_placement_contract():
    """Return the config-owned ordinary-page audit placement contract."""

    contract = dict(COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT)
    contract["ordinary_entrances"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["ordinary_entrances"]
    )
    contract["ordinary_summary_allowed_fields"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["ordinary_summary_allowed_fields"]
    )
    contract["audit_detail_surfaces"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["audit_detail_surfaces"]
    )
    contract["demoted_detail_types"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["demoted_detail_types"]
    )
    contract["ordinary_promotion_required_evidence"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["ordinary_promotion_required_evidence"]
    )
    contract["ordinary_first_view_forbidden_surfaces"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["ordinary_first_view_forbidden_surfaces"]
    )
    contract["audit_demotion_required_evidence"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["audit_demotion_required_evidence"]
    )
    contract["forbidden_audit_demotion_evidence"] = list(
        COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT["forbidden_audit_demotion_evidence"]
    )
    return contract


def get_command_center_runtime_mode_state(default=COMMAND_CENTER_DEFAULT_RUNTIME_MODE):
    """Return the safe runtime-mode selection without exposing raw invalid config."""

    fallback_mode = default if default in COMMAND_CENTER_RUNTIME_MODES else COMMAND_CENTER_DEFAULT_RUNTIME_MODE
    raw_config = get_config_value("COMMAND_CENTER_BOOTSTRAP_MODE")
    raw_mode = str(raw_config if raw_config is not None else fallback_mode).strip().lower()
    source = "default" if raw_config is None else "configured"
    if raw_mode in COMMAND_CENTER_RUNTIME_MODES:
        return {
            "mode": raw_mode,
            "configured_value_safe": raw_mode,
            "valid": True,
            "source": source,
            "redacted_invalid": False,
            "default_mode": fallback_mode,
            "allowed_modes": list(COMMAND_CENTER_RUNTIME_MODES),
            "contains_secret": False,
        }
    return {
        "mode": fallback_mode,
        "configured_value_safe": "[invalid_redacted]",
        "valid": False,
        "source": "configured_invalid_defaulted",
        "redacted_invalid": True,
        "default_mode": fallback_mode,
        "allowed_modes": list(COMMAND_CENTER_RUNTIME_MODES),
        "contains_secret": False,
    }


def _clean_value(value, default=None):
    if value is None:
        return default
    value = str(value).strip()
    return value or default


@lru_cache(maxsize=1)
def _load_local_streamlit_secrets():
    secrets_path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists() or tomllib is None:
        return {}

    try:
        with secrets_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _get_streamlit_secret(name, default=None):
    try:
        import streamlit as st

        return _clean_value(st.secrets.get(name), default)
    except Exception:
        return default


def get_config_value(name, default=None):
    """Read config from Streamlit secrets first, then environment variables."""

    if name not in CONFIG_NAMES:
        return default

    local_secrets = _load_local_streamlit_secrets()
    value = _clean_value(local_secrets.get(name))
    if value:
        return value

    value = _get_streamlit_secret(name)
    if value:
        return value

    return _clean_value(os.environ.get(name), default)


def get_deepseek_keys(extra_keys=None):
    keys = [
        get_config_value("DEEPSEEK_API_KEY"),
        get_config_value("DEEPSEEK_TOKEN_1"),
        get_config_value("DEEPSEEK_TOKEN_2"),
    ]
    keys.extend(extra_keys or [])

    cleaned = []
    for key in keys:
        key = _clean_value(key)
        if key and key not in cleaned:
            cleaned.append(key)
    return cleaned


def get_deepseek_model(purpose="default", default=None):
    """Read DeepSeek model selection from secrets/env without exposing credentials."""

    selected_purpose = str(purpose or "default").strip().lower()
    config_keys = DEEPSEEK_MODEL_CONFIG_KEYS.get(selected_purpose, DEEPSEEK_MODEL_CONFIG_KEYS["default"])
    for key in config_keys:
        value = get_config_value(key)
        if value:
            return value
    if default:
        return _clean_value(default, DEEPSEEK_MODEL_DEFAULTS["default"])
    return DEEPSEEK_MODEL_DEFAULTS.get(selected_purpose, DEEPSEEK_MODEL_DEFAULTS["default"])


def get_deepseek_model_strategy():
    """Return the current model strategy for diagnostics without any token/key material."""

    strategy = {
        purpose: get_deepseek_model(purpose)
        for purpose in DEEPSEEK_MODEL_DEFAULTS
    }
    strategy.update({
        "source": "DEEPSEEK_*_MODEL config or safe defaults",
        "contains_secret": False,
    })
    return strategy


def get_deepseek_factor_explain_mode(default="manual_only"):
    """Return the governed DeepSeek factor explanation mode.

    The mode is intentionally separate from model selection: cache reads and
    page renders must remain no-call regardless of the selected model.
    """

    selected = _clean_value(get_config_value("DEEPSEEK_FACTOR_EXPLAIN_MODE"), default)
    selected = str(selected or default).strip().lower()
    return selected if selected in DEEPSEEK_FACTOR_EXPLAIN_MODES else default


def get_deepseek_auto_explain_enabled(default=False):
    value = _clean_value(get_config_value("DEEPSEEK_AUTO_EXPLAIN_ENABLED"))
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def get_supabase_config():
    return get_config_value("SUPABASE_URL"), get_config_value("SUPABASE_KEY")


def get_tushare_token(default=None):
    """Read Tushare token without exposing it in logs or UI."""

    value = _clean_value(os.environ.get("TUSHARE_TOKEN"))
    if value:
        return value

    local_secrets = _load_local_streamlit_secrets()
    value = _clean_value(local_secrets.get("TUSHARE_TOKEN"))
    if value:
        return value

    return _get_streamlit_secret("TUSHARE_TOKEN", default)


def require_supabase_config():
    url, key = get_supabase_config()
    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not key:
        missing.append("SUPABASE_KEY")
    if missing:
        raise RuntimeError(f"缺少 Supabase 配置：{', '.join(missing)}")
    return url, key


def require_deepseek_keys():
    keys = get_deepseek_keys()
    if not keys:
        raise RuntimeError("缺少 DeepSeek 配置：DEEPSEEK_API_KEY、DEEPSEEK_TOKEN_1 或 DEEPSEEK_TOKEN_2")
    return keys
