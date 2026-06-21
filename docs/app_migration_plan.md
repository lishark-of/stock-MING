# stock-MING App Migration Plan

## 1. Current State

stock-MING is currently a local research decision app with an existing Streamlit legacy/admin/debug surface, a pywebview fallback shell, and an emerging FastAPI / React / Tauri Command Center 3.0 stack. Streamlit is retained as fallback/admin/debug while ordinary workflows migrate; it must not be described as the primary 3.0 runtime surface or target UX until the React/Tauri workflow is demonstrably easier, clearer, and more reliable for normal usage.

综合推演中心 2.0 is now a useful packetized evidence source and transition workspace, not the target ordinary 3.0 UX. Command Center 3.0 should recompose its useful packets into the three ordinary entrances, with research-only status, source state, missing evidence, and last successful cache visible.

The service layer has started to separate business decisions from UI rendering:

- `command_center_service.py` owns refresh contracts, `refresh_level`, `last_success`, `last_error`, stale state, module errors, and `command_center_live_packet`.
- `strategy_execution_service.py` owns the first version of the strategy execution packet by combining existing quant and discipline cache.
- `command_center_decision_engine.py` owns the rule-based daily decision packet.

The app still contains several large functional chains:

- DeepSeek explanation and research flows.
- Tushare, AkShare, yfinance, and Supabase data flows.
- Backtesting and multi-mode backtesting.
- Next ticket radar, including lightweight radar and heavier full scans.
- Margin ETF allocation, ETF data discovery, and ETF research.
- Legacy Streamlit workbench pages.

Heavy tasks remain governed by runtime mode. `cache_only` keeps app open, render, FastAPI startup, and GET cache/status routes fully read-only. `manual` keeps external work behind explicit user buttons or POST tasks. `live_light` may create or reuse a bounded local background POST task after cache render, but provider/model execution still requires ledgers, redaction, task governance, and local fallback/worker boundaries. Full backtests, full-market scans, heavy Tushare/AkShare/yfinance/Supabase refreshes, and real trading paths remain explicit-button or separately authorized work.

## Migration Principle Correction

Command Center 3.0 must not copy the old Streamlit app one-to-one. Legacy parity means preserving useful user capabilities, data sources, signals, evidence chains, and research workflows; it does not mean copying legacy UI, navigation, bugs, historical patchwork, or confusing workflows just because they existed in Streamlit.

Before any major Streamlit workflow enters an ordinary React/Tauri path, run a Legacy Bug / UX Audit and classify it as `KEEP`, `REDESIGN`, `LEGACY-DEBUG`, or `RETIRE`. `KEEP` means useful and reliable enough to preserve with minimal redesign; `REDESIGN` means useful capability but old UX/code should be rebuilt; `LEGACY-DEBUG` means keep only for admin/debug/fallback; `RETIRE` means freeze or remove from ordinary user workflow. Ordinary users should mainly see `今日作战台 / Daily Command Center`, `股票量化推演 / Stock Quant Projection`, and `下一票雷达 / Candidate Radar`; each ordinary entrance must expose next click, Tushare/cache/DeepSeek/pending source state, missing evidence, research-only boundary that is not a buy/sell instruction, blocked/degraded state, and last successful cache/result. Detailed engineering contract tables, receipts, runbooks, and LTG audit surfaces should move to Settings / Developer / Audit unless they are directly needed for comprehension.

`KEEP` promotion requires direct Legacy Bug / UX Audit evidence: an observed user action or workflow problem, the specific legacy bug/confusing UX/patchwork path removed, a data-lineage check, the replacement ordinary entrance, and the frozen legacy path. Seed-only docs/config/scaffold, route inventory, local receipts, and no-feature-loss matrices are useful orientation, but they cannot make a legacy module ordinary-user-ready by themselves.

The shared audit vocabulary is config-owned by `COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT` via `get_command_center_legacy_audit_classification_contract()`. It fixes `keep_requires_direct_legacy_bug_ux_audit_evidence`, `seed_inventory_receipt_matrix_or_docs_config_cannot_promote_keep`, and `ordinary_entry_requires_replacement_entrance_and_frozen_legacy_path`, while staying `legacy_audit_classification_contract_is_not_production_evidence`. This is a migration gate for old Streamlit workflows, not a production proof or a reason to copy old UI/code.

The same contract fixes the direct-evidence status gate: `direct_evidence_row_required_before_keep_or_ordinary_entry`, `seed_only_rows_default_to_redesign_legacy_debug_or_retire`, `unclear_data_lineage_blocks_ordinary_entry_until_redesigned_or_frozen`, and `audit_scope_tracks_workflow_group_not_legacy_file_or_tab_count`. A row can become `direct_evidence_ready` only after the direct audit fields are filled; `blocked_by_lineage` keeps it out of ordinary flow. `route_inventory_only`, `legacy_tab_name_only`, `docs_config_scaffold_only`, `local_receipt_only`, `no_feature_loss_matrix_only`, and `mock_sanitizer_or_preflight_only` remain forbidden sources for `KEEP`.

Legacy Audit row evidence is now pinned by `legacy_audit_row_requires_scope_status_direct_source_lineage_replacement_and_freeze_decision`: each old ordinary workflow row must carry `workflow_group`, `legacy_surface_or_module`, `observed_user_action_or_workflow_problem`, `direct_ux_bug_evidence_source`, `classification`, `evidence_status`, `data_lineage_check`, `replacement_ordinary_entrance`, `frozen_legacy_path`, `ordinary_entry_decision`, and `next_action`. `file_inventory_only`, `legacy_tab_count_only`, `route_exists_only`, `local_receipt_only`, `docs_config_scaffold_only`, and `no_feature_loss_matrix_only` cannot complete the row.

The seed row list is config-owned by `legacy_audit_seed_rows_cover_ordinary_workflow_scope_without_keep_promotion` and remains governed by `legacy_audit_seed_rows_are_not_direct_evidence_or_production_evidence`. It covers `streamlit_home_daily_summary`, `legacy_single_stock_room_quant_projection`, `legacy_candidate_radar`, `legacy_next_session_chart`, `legacy_factor_risk_provider_health_tables`, `legacy_discipline_backtest_lab`, `legacy_margin_etf_leverage_flow`, and `legacy_external_brain_ai_advisor`; those rows stay at `not_promoted_seed_only`, `not_promoted_legacy_debug`, or `not_promoted_retire` until direct UX/bug evidence is attached.

The classification transition rules are `seed_only_cannot_transition_to_keep`, `direct_evidence_ready_can_transition_to_keep_only_with_all_required_fields`, `blocked_by_lineage_transitions_to_redesign_legacy_debug_or_retire`, `known_bug_or_patchwork_without_replacement_stays_redesign_or_retire`, and `legacy_debug_and_retire_do_not_enter_ordinary_user_flow`. Ordinary entry can only follow `KEEP` or `REDESIGN_WITH_REPLACEMENT_READY`; `REDESIGN_WITHOUT_REPLACEMENT_READY` remains outside ordinary flow. `keep_requires_direct_evidence_and_no_open_bug_or_lineage_blocker` and `redesign_requires_replacement_workflow_before_ordinary_entry` keep this as a product workflow migration rule rather than old file parity.

Streamlit remains governed by `streamlit_remains_fallback_admin_debug_until_react_tauri_workflow_is_easier_clearer_more_reliable` and `streamlit_must_not_be_primary_3_0_runtime_or_target_ux`. Fallback retirement requires `fallback_retirement_requires_replacement_workflow_direct_evidence_and_rollback_plan`, with `react_tauri_replacement_workflow_ready`, `ordinary_entry_easier_clearer_more_reliable_evidence`, `direct_legacy_bug_ux_audit_complete`, `provider_model_cache_pending_state_visible`, `last_successful_cache_or_result_visible`, and `rollback_or_admin_debug_path_retained_until_promotion`. `streamlit_ui_polish_only`, `stage_scope_manifest_only`, route inventory, local receipts, docs/config scaffold, and no-feature-loss matrices cannot retire fallback.

Ordinary entrances should share one source-state chip vocabulary: `cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result`. The chips must tell a normal user whether the visible state is local cache, provider-backed/provider-pending market data, explanation-only model output, missing/waiting evidence, stale/failed/partial source, or the latest safe fallback. Rendering these chips is read-only planning language; it must not create tasks, call provider/model, write cache/config, or promote production evidence.

That chip vocabulary is now config-owned by `COMMAND_CENTER_ORDINARY_SOURCE_STATE_CONTRACT` via `get_command_center_ordinary_source_state_contract()`. It fixes `read_only_source_state_chips_in_ordinary_summary`, `provider_backed_or_provider_pending_market_data_with_call_ledger_status`, `explanation_only_model_output_never_data_source_or_action_writer`, and `pending_or_degraded_state_must_show_missing_evidence_or_blocker`. The chips remain `source_state_chips_never_create_tasks`, `source_state_chips_never_write_cache_or_config`, and `source_state_contract_is_not_provider_model_or_production_evidence`.

The per-entrance state fields are config-owned by `COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT` via `get_command_center_ordinary_source_state_display_contract()`. It requires `provider_model_cache_pending_states_must_be_visible_in_ordinary_summary`, `tushare_state_requires_call_ledger_or_provider_pending_marker`, `deepseek_state_is_explanation_only_with_model_ledger_or_pending_marker`, `cache_state_must_show_freshness_and_last_successful_pointer`, and `pending_state_must_name_missing_evidence_or_next_allowed_task`. The display rows are `ordinary_source_state_display_never_creates_tasks` and stay `ordinary_source_state_display_contract_is_not_provider_model_or_production_evidence`.

Ordinary page visibility for provider/model/cache/pending state now requires `ordinary_source_state_page_visibility_requires_provider_model_cache_pending_last_successful_and_blocker_rows`: `source_state_visible_in_ordinary_summary`, `cache_freshness_and_last_successful_pointer_visible`, `tushare_call_ledger_or_provider_pending_marker_visible`, `deepseek_model_ledger_or_pending_marker_visible`, `pending_missing_evidence_or_next_allowed_task_visible`, `degraded_blocker_and_safe_fallback_visible`, `no_trade_no_action_boundary_visible_next_to_state`, and `settings_developer_audit_link_for_detail_visible`. `ordinary_source_state_cannot_promote_from_hidden_tabs_tooltips_or_engineering_tables_only` blocks `engineering_audit_table_only`, `settings_detail_only`, `tooltip_only`, `hidden_tab_only`, `local_receipt_only`, or `docs_config_scaffold_only` from proving ordinary page clarity.

Ordinary entrances should also share one next-click rule: show one primary safe action, and show a clear disabled/degraded reason when the action is not available. `Daily Command Center` should route the user to today's cache/decision summary or missing-evidence review; `Stock Quant Projection` should route a confirmed symbol to `生成 3.0 量化推演`; `Candidate Radar` should route to the last radar cache or a button-gated quick scan create/reuse path. Search typing, React render, mode banners, source-state chips, DeepSeek text, and radar candidates must not behave as hidden next-click actions. Any work-creating action remains POST task / worker / local fallback only, with task status and no-trade/no-action boundaries visible.

That next-click rule is config-owned by `COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT` via `get_command_center_ordinary_next_click_contract()`. It fixes `one_primary_safe_action_per_ordinary_entrance`, `disabled_or_degraded_reason_visible_before_click`, `work_creating_next_click_must_use_post_task_worker_or_local_fallback`, and `work_creating_next_click_must_show_task_status`. The contract keeps typing/render/banner/chip/model text/radar candidate as non-actions, preserves `next_click_is_research_only_no_buy_sell_instruction`, and remains `ordinary_next_click_contract_is_not_execution_or_production_evidence`.

Daily Command Center's ordinary workflow is config-owned by `COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT` via `get_command_center_daily_command_ordinary_workflow_contract()`. It keeps today's focus pool, risk summary, cache status, provider-health summary, missing-evidence prompt, and last successful cache visible while requiring `daily_command_center_shows_today_summary_before_engineering_detail`, `daily_summary_missing_evidence_must_be_visible`, and `last_successful_daily_cache_must_remain_visible`. Provider-health detail follows `provider_health_detail_moves_to_settings_config_health_or_audit`, page render remains `daily_command_center_ordinary_workflow_never_creates_tasks_on_render`, and the row is `daily_command_center_ordinary_workflow_contract_is_not_provider_model_or_production_evidence`.

Candidate Radar's ordinary workflow is config-owned by `COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT` via `get_command_center_candidate_radar_ordinary_workflow_contract()`. It keeps Top/Watch/Excluded candidate groups, scoring reason, scan scope, candidate pool source, and no-feature-loss visibility while requiring `quick_scan_must_be_button_gated_post_task_or_local_fallback`, `last_radar_cache_visible_before_scan_action`, and `missing_full_pool_deep_scan_browser_ci_or_provider_evidence_must_be_visible`. Page render must remain `candidate_radar_ordinary_workflow_never_creates_tasks_on_render`, and the row is `candidate_radar_ordinary_workflow_contract_is_not_production_replacement_evidence`.

Candidate Radar promotion to a user-usable ordinary entry requires `candidate_radar_user_usable_entry_requires_cache_scope_source_gap_and_no_buy_boundary`: `last_radar_cache_visible`, `scan_scope_and_candidate_pool_source_visible`, `top_watch_excluded_groups_visible`, scoring reason, `provider_cache_pending_or_degraded_state_visible`, visible missing evidence, `candidate_is_not_buy_instruction_visible`, and `quick_scan_button_or_disabled_reason_visible`. The rule `candidate_radar_cannot_promote_from_legacy_ui_or_local_receipt_only` blocks `old_streamlit_radar_ui_parity_only`, `legacy_fallback_path_only`, local receipts, no-feature-loss matrices, stage-scope manifests, or `browser_artifact_without_provider_or_worker_evidence` from becoming replacement evidence.

Research-only wording is also config-owned by `COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT` via `get_command_center_ordinary_research_boundary_contract()`. It fixes `research_only_not_buy_sell_instruction`, `show_research_only_boundary_in_ordinary_summary`, `deepseek_text_is_explanation_only_not_data_source_or_action`, `factor_scores_are_research_evidence_not_trade_action`, and `operation_zones_are_conditions_not_orders`. The boundary requires `never_modify_strategy_action_prices_positions_factors_or_operation_zones` and remains `research_boundary_contract_is_not_execution_or_production_evidence`.

Missing-evidence and fallback wording is config-owned by `COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT` via `get_command_center_ordinary_evidence_fallback_contract()`. It fixes `missing_evidence_must_be_visible_before_action`, `blocked_state_must_show_blocker_and_allowed_next_step`, `degraded_state_must_show_stale_failed_or_partial_source`, and `last_successful_cache_or_result_must_remain_visible_as_fallback`. Fallback rows remain `fallback_is_display_only_not_current_provider_model_evidence`, must be `evidence_fallback_display_never_creates_tasks`, and stay `evidence_fallback_contract_is_not_provider_model_or_production_evidence`.

Ordinary-page audit placement is config-owned by `COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT` via `get_command_center_ordinary_audit_placement_contract()`. It fixes `ordinary_pages_show_user_summary_before_engineering_audit_details`, `detailed_engineering_audit_tables_move_to_settings_developer_audit`, and `engineering_contract_tables_must_not_dominate_ordinary_pages`. The placement row is `audit_placement_display_never_creates_tasks` and stays `ordinary_audit_placement_contract_is_not_production_evidence`; ordinary pages keep user-facing summary rows, while engineering details move behind Settings / Developer / Audit unless they explain the current decision surface.

Ordinary-entry promotion must satisfy `ordinary_entry_promotion_requires_user_summary_fields_before_engineering_detail` and `ordinary_first_view_shows_next_click_state_gaps_boundary_and_last_success_before_audit`. Required first-view evidence includes `next_click_visible_before_audit_detail`, `source_state_visible_before_audit_detail`, `missing_evidence_visible_before_audit_detail`, `research_only_boundary_visible_before_audit_detail`, `last_successful_cache_or_result_visible_before_audit_detail`, and `settings_developer_audit_link_visible_for_details`. `engineering_contract_table_as_primary_surface`, `receipt_rows_as_primary_surface`, and `legacy_route_inventory_as_primary_surface` are forbidden as the primary ordinary-user surface.

Audit demotion for ordinary pages now requires `ordinary_first_view_must_not_be_engineering_audit_dashboard`: `ordinary_summary_rendered_before_any_engineering_table`, `engineering_contract_tables_demoted_to_settings_developer_audit`, `receipt_rows_demoted_to_settings_developer_audit`, `runbooks_demoted_to_settings_developer_audit`, `ltg_audit_surfaces_demoted_to_settings_developer_audit`, `current_decision_surface_exception_reason_visible_when_detail_stays`, and `settings_developer_audit_link_visible_after_summary`. `audit_table_before_user_summary`, `receipt_rows_before_next_click`, `runbook_before_source_state`, `ltg_audit_as_default_page_body`, `all_details_hidden_without_audit_link`, `local_receipt_only`, or `docs_config_scaffold_only` cannot count as ordinary-page audit demotion evidence.

普通入口任务边界 must stay visible in the user summary area, not only in engineering audit tables. `今日作战台 / Daily Command Center`, `股票量化推演 / Stock Quant Projection`, and `下一票雷达 / Candidate Radar` should show `任务边界` before Settings / Developer / Audit details. The boundary is: `GET cache` / React render 只读; `manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback; pages must not directly call Tushare、DeepSeek、GitHub 或交易路径 during render. This is a migration-plan and runtime-mode wording guard, not production evidence, and it does not mean the full `live_light` workflow is implemented.

`股票量化推演 / Stock Quant Projection` may also show a read-only runtime-mode banner from `GET /api/bootstrap/status` in its ordinary summary, using the same `cache_only/manual/live_light/live_full` vocabulary as the home and radar pages. That banner is only a visibility aid: it must not create `POST /api/bootstrap/live-startup`, call provider/model, write config/cache, expose token/key, or upgrade a local receipt into production evidence.

The migration plan references `runtime_mode_policy_rows` as the shared config/status vocabulary for this boundary. Those rows must carry `cache_get_rule`, `react_render_rule`, `ledger_rule`, `ordinary_entrance_visibility_rule`, `ordinary_mode_banner_rule`, and `production_evidence_rule` so app planning can verify GET cache / React render read-only behavior, call/model ledger requirements for `manual` or `live_light` external work, ordinary-entry `任务边界` visibility before Settings / Developer / Audit, ordinary mode banner read-only status display rather than task launching or config writing, and config policy rows remaining non-production evidence.

Runtime mode display also has a separate config-read contract: `COMMAND_CENTER_RUNTIME_MODE_CONFIG_CONTRACT` via `get_command_center_runtime_mode_config_contract()`. The contract keeps `COMMAND_CENTER_BOOTSTRAP_MODE` safe for ordinary summaries by requiring `redact_invalid_value_and_fallback_to_cache_only` / `[invalid_redacted]` for invalid configured values, `read_only_mode_banner_no_frontend_edit_or_writeback` for UI display, `reserved_disabled_requires_separate_authorization` for `live_full`, and `runtime_config_contract_is_not_production_evidence`. Showing this contract is not a task launcher, provider/model executor, config writer, or production `live_light` proof.

The operator-facing config口径 is: server config is the source of truth; `GET /api/bootstrap/status` may show safe defaults, configured source switches, effective mode-gated switches, profile/scope labels, budget limits, and release-switch state, but it must remain read-only, non-editable, no-writeback, no-secret, and non-production evidence. A configured source switch or release switch is not the same thing as an effective external call. `cache_only` forces effective automation false even if every live switch is configured true; `manual` keeps execution behind an explicit button/POST task; `live_light` may only create bounded local POST tasks after cache render; `live_full` stays reserved and disabled until separately authorized.

| config group | migration-plan interpretation |
|---|---|
| `COMMAND_CENTER_BOOTSTRAP_MODE` | Runtime vocabulary only; invalid values redact and fall back to `cache_only`. |
| `COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN` / `COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN` | Source-switch intent; effective only in `live_light` and never from GET/cache/render/startup/search typing. |
| `COMMAND_CENTER_LIVE_STARTUP_AUTOSTART` | Local bootstrap task-create/reuse guard after cache render, not provider/model authorization. |
| `COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART` | Safe searched-symbol submit guard for local quant-projection receipt task, not search typing automation. |
| `COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE` / `COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE` | Plan metadata for future light provider/model stages; not an executor or production evidence. |
| `COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT` / `COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT` | Default-off release switches; effective false until execution-request, real ledgers, browser evidence, redaction, rollback, and promotion gates pass. |
| `COMMAND_CENTER_LIVE_ALLOW_FULL_POOL` | Reserved full-pool/deep-scan switch; no hidden `live_full` automation in this migration phase. |

The bounded startup task wording is owned by `COMMAND_CENTER_LIVE_LIGHT_BOOTSTRAP_TASK_CONTRACT` via `get_command_center_live_light_bootstrap_task_contract()`. It fixes `after_initial_cache_render_only`, `create_or_reuse_one_rate_limited_local_task_after_cache_render`, and `one_active_or_recent_task_per_session_and_rate_window` as the only planned `live_light` startup automation shape. Provider/model work still follows `future_provider_model_execution_requires_execution_request_and_ledgers`, and the row is `bootstrap_task_contract_is_not_execution_or_production_evidence`; it is not frontend wiring, not a provider/model call, and not production readiness.

Searched-symbol quant projection has its own config-owned task wording: `COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT` via `get_command_center_search_quant_projection_task_contract()`. It fixes `生成 3.0 量化推演` as `explicit_confirmed_symbol_submit_or_live_light_safe_submit`, gated by `manual_explicit_button_or_live_light_effective_search_submit_autostart`, with `confirmed_single_a_share_symbol_normalize_suffix_and_drop_raw_query` and `create_or_reuse_local_quant_projection_receipt_task_only`. Real provider/model acceptance remains `provider_model_acceptance_requires_dry_run_execution_request_and_ledgers`, so the contract is `search_quant_projection_contract_is_not_provider_model_or_production_evidence`.

The ordinary searched-symbol workflow is config-owned by `COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT` via `get_command_center_stock_quant_projection_ordinary_workflow_contract()`. It makes `生成 3.0 量化推演` available only after `confirmed_single_a_share_symbol_required_before_submit`; `search_typing_never_creates_task_or_provider_model_call` keeps typing/render safe, and `render_cache_then_show_task_status_and_last_successful_result` keeps the page nonblocking. Missing provider/model/factor/next/ECharts/browser evidence must stay visible through `missing_provider_model_factor_next_echarts_or_browser_evidence_must_be_visible`, while `stock_quant_projection_ordinary_workflow_never_creates_tasks_on_typing_or_render` and `stock_quant_projection_ordinary_workflow_contract_is_not_provider_model_or_production_evidence` keep this as ordinary-path guidance rather than production proof.

Stock Quant Projection promotion into a user-usable ordinary entry now requires `stock_quant_projection_user_usable_entry_requires_confirmed_symbol_cache_task_status_and_research_boundary`: `confirmed_single_a_share_symbol_visible`, `generate_3_0_quant_projection_button_or_disabled_reason_visible`, `cache_result_or_last_successful_result_visible`, `task_status_visible_after_submit`, `provider_model_cache_pending_state_visible`, `factor_next_echarts_or_browser_missing_evidence_visible`, optional explanation-only `deepseek_explanation_status_is_optional_and_explanation_only_visible`, and `research_only_no_buy_sell_or_strategy_action_boundary_visible`. `stock_quant_projection_cannot_promote_from_search_typing_ai_text_or_local_receipt_only` blocks `search_typing_only`, `ai_text_as_action_only`, `local_quant_projection_receipt_only`, `provider_model_scope_ticket_only`, `legacy_single_stock_room_ui_parity_only`, or `docs_config_scaffold_only` from acting as promotion evidence.

The three ordinary-entry contracts are indexed by `COMMAND_CENTER_ORDINARY_WORKFLOW_REGISTRY_CONTRACT` via `get_command_center_ordinary_workflow_registry_contract()`. The registry keeps `three_ordinary_entrances_are_the_primary_user_workflow`, `ordinary_registry_rows_appear_before_settings_developer_audit`, and `each_registered_entrance_shows_next_click_source_state_missing_evidence_research_boundary_blocked_degraded_and_last_successful_result` in one place. It is `ordinary_workflow_registry_never_creates_tasks` and stays `ordinary_workflow_registry_contract_is_not_production_evidence`.

Every future migration checkpoint must answer what user capability was preserved, what legacy UX problem was removed, which legacy bug or patchwork path was intentionally not migrated, what became simpler for a non-technical user, and which real blocker was reduced. `COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT` via `get_command_center_migration_checkpoint_contract()` owns this gate as `every_future_migration_checkpoint_must_answer_five_questions`, with the required answers named `what_user_capability_was_preserved`, `what_legacy_ux_problem_was_removed`, `what_legacy_bug_or_patchwork_path_was_not_migrated`, `what_became_simpler_for_nontechnical_user`, and `which_real_blocker_was_reduced`. Broad contracts, receipts, runbooks, or manifests must satisfy `broad_contract_receipt_runbook_or_manifest_requires_named_release_blocker`; this remains `migration_checkpoint_contract_is_not_production_evidence`, so the strategy correction is not production acceptance evidence and does not complete any LTG by itself.

The checkpoint contract also fixes the current priority order as `fix_push_gate_ci_evidence`, `legacy_bug_ux_audit_for_streamlit_ordinary_workflows`, `rebuild_ltg13_candidate_radar_user_usable_workflow`, `searched_symbol_to_generate_3_0_quant_projection`, `show_provider_model_cache_pending_state_on_page`, and `move_engineering_audit_tables_out_of_ordinary_flow`. Future slices must obey `future_migration_slices_follow_current_priority_order_or_name_blocker_exception`; `remote_ci_unverified_remains_release_blocker_until_current_green_or_reviewed_logs` keeps release claims blocked until current CI evidence exists, `legacy_bug_ux_audit_precedes_major_ordinary_workflow_migration` keeps Streamlit modules from blind promotion, and `ordinary_user_workflow_slices_precede_extra_engineering_scaffold` keeps ordinary-user clarity ahead of extra engineering tables.

For release evidence, the checkpoint contract requires `matching_head_sha_or_commit`, `current_remote_actions_green_or_failed_step_reviewed`, `fresh_local_push_gate_result_for_current_head`, `safe_failure_log_excerpt_or_green_run_url`, and `explicit_user_push_confirmation_before_push`. `local_unit_tests_only`, `checkpoint_answer_only`, `static_workflow_file_presence_only`, `ci_failure_email_without_matching_run_logs`, `old_remote_green_run_for_different_head`, and `local_receipt_or_stage_scope_manifest_only` are non-evidence for remote CI. Keep `release_or_production_replacement_claim_requires_current_remote_ci_green_or_reviewed_failure_logs`, `push_requires_explicit_user_confirmation_after_local_gate_review`, and `ci_checkpoint_contract_never_calls_github_or_fetches_actions_logs` visible; `treating_local_gate_or_checkpoint_as_remote_ci_green` is not allowed.

Remote CI review rows must satisfy `remote_ci_review_row_requires_head_status_log_local_gate_push_decision`: `head_sha_or_commit`, `remote_run_url_or_id`, `remote_status`, `failed_step_or_green_status`, `safe_failure_log_excerpt_or_green_run_url`, `local_gate_result_for_same_head`, `push_confirmation_state`, `release_claim_decision`, and `next_action`. `old_run_without_matching_head`, `email_subject_only`, `local_gate_pass_only`, `workflow_yaml_presence_only`, `unreviewed_failed_step`, and `unchecked_artifact_or_secret_scan` cannot complete CI evidence.

The current P0 seed row is `remote_ci_review_seed_row_keeps_p0_blocked_until_matching_remote_run_review`: keep `pending_current_head_sha`, `pending_remote_actions_run`, `remote_ci_unverified`, `not_reviewed`, `pending_safe_log_excerpt_or_green_run_url`, `pending_fresh_local_push_gate_for_current_head`, `not_requested_no_push`, and `blocked_remote_ci_unverified` until a matching remote run is reviewed. The seed row is a blocker template only, not remote CI evidence.

## 2. Migration Goals

The migration should make stock-MING feel more like a stable local product and less like a web page embedded in a shell. The goals are:

- Build a more native App experience.
- Reduce visible Streamlit web-app feel.
- Make startup more stable and diagnosable.
- Improve the left navigation and first-screen decision experience.
- Keep the research decision loop clear: read or refresh governed data, show research-only strategy context and daily decision packets, and optionally ask DeepSeek to explain existing evidence without issuing buy/sell instructions.
- Preserve useful capabilities, data sources, signals, evidence chains, and research workflows while the legacy workbench remains fallback/admin/debug.
- Redesign or freeze confusing legacy UX, known bug paths, unclear data lineage, and historical patchwork before they enter an ordinary React/Tauri workflow.
- Avoid a full rewrite that creates white screens, performance regressions, data refresh regressions, or feature loss.

## 3. Options Compared

### Option A: pywebview + Streamlit fallback hardening

This option keeps pywebview + Streamlit only as a fallback/admin/debug safety path. It may improve desktop-shell diagnostics, error handling, and legacy entry clarity, but it must not become the ordinary-user migration target or a reason to polish confusing Streamlit workflows into Command Center 3.0.

- Development cost: low to medium. Most work is incremental.
- Reuse boundary: service packets, data adapters, evidence chains, governed DeepSeek/Tushare paths, backtest engines, radar signal definitions, and ETF research inputs can remain referenceable. Streamlit rendering code, confusing navigation, buggy flows, and historical patchwork must not be reused as ordinary 3.0 UX.
- Current feature stability: high for fallback/admin/debug recovery only. It changes little about the legacy execution model, so it cannot prove the React/Tauri ordinary workflow is clearer or ready.
- App native feel: limited but improvable. pywebview can hide some browser feel, improve window title, menu/Dock naming, and provide a more focused shell, but Streamlit still leaks through in layout and runtime behavior.
- Packaging complexity: medium. It still depends on local Python, `.venv`, Streamlit subprocess management, and macOS wrapper details.
- White screen risk: lower than a rewrite, but still present if Streamlit subprocess startup fails or pywebview cannot reach the local port.
- Impact on DeepSeek / Tushare / AkShare / Supabase: minimal. Existing gated flows stay intact.
- Fit: short-term fallback safety path only. It helps keep local work recoverable while React/Tauri ordinary entrances mature, but user-facing migration work should still move toward packet/API-backed 3.0 workflows.

### Option B: Tauri + React frontend + Python local API

This option builds a native desktop shell with a React frontend and moves Python business logic behind a local API.

- Development cost: high. It introduces a new frontend, local API boundary, packaging flow, and desktop runtime.
- Code reuse rate: medium. Pure service modules can be reused if their outputs remain JSON-friendly, but Streamlit rendering code cannot be reused directly.
- Current feature stability: medium to low during migration. The core command center can migrate first, but legacy pages would need to remain in Streamlit until replaced.
- App native feel: high. Tauri provides a lighter, more native desktop experience than an embedded Streamlit surface.
- Packaging complexity: high. Python runtime bundling, local API startup, process supervision, logs, permissions, and update paths must be designed carefully.
- White screen risk: medium during pilot, high if attempted as a full rewrite. The UI may load while the Python API fails, or the API may block on heavy tasks if gating is not preserved.
- Service packetization requirement: high. The frontend should consume `command_center_live_packet`, `strategy_execution_packet`, `command_center_decision_packet`, and future packets without importing Streamlit or Python UI code.
- Fit: good long-term direction, but only after more adapters and local API contracts exist.

### Option C: PWA / Web App

This option turns stock-MING into a browser-first app, potentially installable as a progressive web app.

- Development cost: medium to high, depending on how much of the current Python runtime is preserved behind an API.
- Cross-platform ability: high for the UI surface, but limited for local Python-heavy workflows.
- Local data and local Python limits: significant. Tushare, AkShare, local files, local caches, backtests, and desktop-specific workflows would need a backend service or remote hosting.
- Impact on market refresh, Tushare, AkShare, and local files: major. Browser-only execution cannot safely replace the current local Python data stack.
- Fit: not ideal for the current project. A PWA may be useful later as a companion dashboard, but not as the main migration path while local Python and local data chains remain central.

### Option D: Electron + React + Python backend

This option uses Electron for the desktop shell, React for the frontend, and a Python backend for business logic.

- Development cost: high, similar to Tauri plus a larger JavaScript runtime surface.
- Ecosystem maturity: very high. Electron has mature packaging, debugging, and desktop app conventions.
- Package size: large. Electron apps usually ship with a heavier runtime than Tauri.
- Native experience: good, though often heavier than Tauri.
- Maintenance cost: medium to high. The app would need to maintain Node/Electron, React, Python backend, packaging, and inter-process coordination.
- Compared with Tauri: Electron is more mature and forgiving, while Tauri is lighter and better aligned with a focused local desktop tool if the team can handle the packaging complexity.
- Fit: viable long-term fallback if Tauri packaging becomes a blocker, but not the preferred first native pilot.

## 4. Recommended Strategy

Short term: keep pywebview + Streamlit available as fallback/admin/debug while hardening startup diagnostics and making the command center packet/API path more product-like. Preserve useful research capabilities without promoting confusing legacy workflows into the ordinary user path.

Medium term: gradually extract command center adapters from `app.py` so the UI consumes packets instead of owning orchestration. Keep service modules UI-free and keep packet outputs JSON-friendly.

Long term: prioritize a Tauri + React + Python local API pilot around the three ordinary entrances: `今日作战台 / Daily Command Center`, `股票量化推演 / Stock Quant Projection`, and `下一票雷达 / Candidate Radar`. This pilot should prove those user paths are easier, clearer, and more reliable before any broader legacy-workbench migration; do not migrate the entire legacy workbench at once.

不建议现在直接全量迁移到 React/Tauri。

The reasons are:

- `app.py` still owns a large amount of legacy page logic.
- DeepSeek, backtesting, Tushare full scans, next ticket full scans, ETF discovery, and data refresh chains are complex.
- Service-layer packetization does not yet cover every module and every old workbench path.
- A full migration can easily introduce white screens, performance regressions, data refresh bugs, packaging failures, and feature regressions.

The safer path is to keep Streamlit as the reliable fallback/admin/debug surface, not the primary 3.0 surface, while progressively making the command center API-like, then use that stable packet surface for a native pilot.

## 5. Phased Roadmap

### Phase 1: Desktop shell hardening

- Add startup self-checks.
- Show a clear message when `.venv` is missing.
- Show a clear message when ports are occupied.
- Add a Streamlit subprocess error page instead of a blank desktop window.
- Add App icon support.
- Make macOS menu and Dock names consistently show stock-MING.
- Default into a clear 3.0 entry / transition screen that points ordinary users toward the three ordinary entrances or the legacy fallback, not deeper Streamlit tab navigation.
- Preserve runtime-mode automation boundaries: startup self-checks and shell diagnostics stay cache/render safe, while any later `live_light` background work must still enter through bounded POST tasks.

### Phase 2: Command center adapter extraction

- Extract command center adapter logic from `app.py`.
- Keep the Streamlit UI reachable only as fallback/admin/debug while adapters are extracted; it is not the ordinary 3.0 UX target.
- Keep service modules free of UI imports.
- Keep packets JSON-friendly.
- Do not bypass DeepSeek, Tushare, AkShare, Supabase, or backtest governance; any provider/model evolution must be a separate audited task slice with safe params, ledgers, redaction, and no-trade/no-action boundaries.

### Phase 3: Local API layer

- Establish a local API layer for packet consumption.
- Expose only lightweight packet endpoints by default.
- Keep GET packet/cache endpoints read-only in every mode.
- Allow `manual` to run selected external work only through explicit POST tasks.
- Allow `live_light` only for bounded local background task creation after cache render, with provider/model execution still behind ledgers, redaction, and task governance.
- Keep backtests, Tushare full scans, full-market scans, and other heavy provider refreshes explicit-button or separately authorized.

### Phase 4: Tauri / React pilot

- Rebuild the three ordinary entrances in Tauri + React: `今日作战台 / Daily Command Center`, `股票量化推演 / Stock Quant Projection`, and `下一票雷达 / Candidate Radar`.
- Consume packet/cache/task status surfaces for next click, source state, missing evidence, research-only boundary, blocked/degraded state, and last successful result.
- Do not migrate the old workbench in this phase.
- Keep the old Streamlit app available as an advanced legacy mode.

### Phase 5: Audit-gated workflow migration

- Build the searched-symbol -> `生成 3.0 量化推演` path as a clear nonblocking workflow.
- Rebuild Candidate Radar as a user-usable workflow before any production replacement claim.
- Show provider/model/cache/pending state directly in the ordinary entrances.
- Move detailed engineering contract tables, receipt rows, runbooks, and LTG audit surfaces to Settings / Developer / Audit.
- Keep margin ETF, trading discipline, backtest labs, provider health, and external-memory tools in `LEGACY-DEBUG` unless a new Legacy Bug / UX Audit reclassifies them for a redesigned ordinary flow.
- Retire or freeze old model-advice paths that read like buy/sell instructions rather than research explanations.

### Phase 6: Legacy Streamlit retirement decision

- Decide whether to hide or retire the old Streamlit workbench only after the core command center chain is stable in the native surface.
- Keep a rollback path until the native path has covered the real daily workflow.

## 6. Architecture Principles

- Service modules must not contain UI rendering.
- Frontends should consume packets, not reach into Streamlit page state.
- Packets must be JSON-friendly.
- Runtime mode owns automation boundaries: `cache_only` is read-only, `manual` is explicit-button/POST only, `live_light` is bounded local background POST task only, and `live_full` is reserved until separately authorized.
- GET cache/status routes, React render, FastAPI startup, and search typing must not call providers, models, workers, or trading paths.
- DeepSeek is an explanation model only, not a data source, and must not overwrite prices, holdings, factors, operation zones, or strategy action.
- Backtests, full-market scans, heavy provider refreshes, and real trading remain explicit-button or separately authorized work.
- The legacy Streamlit entry must not be broken during migration.
- Every migration phase must preserve a fallback path.

## 7. Risk Register

- `app.py` is still too large and mixes routing, rendering, orchestration, DeepSeek wrappers, and legacy workbench logic.
- `visual_components.py` can continue growing into another large mixed-responsibility file.
- Streamlit menus and browser-like affordances cannot be fully native.
- Missing `.venv` can still make the desktop shell fail at startup.
- pywebview or the Streamlit subprocess can still produce a blank window if startup fails.
- A full Tauri/React migration has high cost and high regression risk.
- A local API layer introduces security and process-boundary concerns.
- DeepSeek calls have cost, latency, and failure handling risks.
- Tushare and AkShare external data can be unstable or slow.
- Backtests and full scans can cause visible lag if accidentally triggered.

## 8. Immediate Next Steps

1. Fix push gate / CI evidence before any release or production-replacement claim; local gate or checkpoint evidence is not a substitute for a current matching remote CI green result or reviewed failure logs.
2. Keep the Legacy Bug / UX Audit current for old Streamlit ordinary workflows before moving any module into a 3.0 ordinary entrance.
3. Rebuild LTG-13 Candidate Radar as a user-usable workflow with source state, missing evidence, last cache/result, and research-only boundaries visible.
4. Build the searched-symbol -> `生成 3.0 量化推演` path as a clear nonblocking workflow through task/cache/status surfaces.
5. Show provider/model/cache/pending state clearly on the page in the three ordinary entrances.
6. Move excessive engineering audit tables, receipt rows, runbooks, and LTG audit detail away from ordinary user flow and into Settings / Developer / Audit; ordinary pages should keep only user-facing summary, source state, missing-evidence, blocked/degraded, last-cache/result, and next-action rows unless an engineering detail directly explains the current decision surface.

## 9. Non-goals

- Do not fully rewrite the frontend in this stage.
- Do not remove Streamlit fallback/admin/debug during this stage.
- Do not remove the legacy workbench rollback path, but do not promote it as an ordinary 3.0 entrance.
- Do not bypass service contracts, task governance, ledgers, redaction, or mode gates.
- Do not route DeepSeek, Tushare, AkShare, Supabase, or backtest work around explicit POST task / worker / local fallback boundaries.
- Do not treat docs/config/scaffold/preflight/local receipt, matrix, mock, or sanitizer evidence as production acceptance evidence.
- Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests unless they directly reduce a current release blocker.
- Do not promote provider/model/backtest changes as production evidence without direct acceptance, safety scans, and no-trade/no-action review.
- Do not add automated trading.
- Do not add automatic heavy-position recommendations.
