from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore
from server.services import packet_service, task_service, tushare_task_service


PACKET_KEY = "command_center_3_candidate_radar_cache"
SCHEMA_VERSION = "candidate_radar_cache.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
CANDIDATE_BROWSER_QA_RUNBOOK_PATH = PROJECT_ROOT / "scripts" / "candidate_radar_browser_qa_runbook.py"
MOTION_BROWSER_QA_RUNNER_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runner.mjs"
MOTION_QA_ARTIFACT_ROOT = PROJECT_ROOT / ".stock_ming_3" / "motion_qa"
CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH = (
    PROJECT_ROOT
    / ".stock_ming_3"
    / "candidate_radar_worker"
    / "candidate_radar_worker_filesystem_roundtrip_smoke.json"
)
CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH = (
    PROJECT_ROOT
    / ".stock_ming_3"
    / "candidate_radar_provider_parity"
    / "tushare_light_provider_ledger.json"
)
CANDIDATE_ROUTE_SOURCE_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
SUPPORTED_LOCAL_SCAN_MODES = {"quick_cache_scan", "watchlist_scan", "custom_pool_scan", "full_pool_local_scan"}
LOCAL_POOL_SCAN_MODES = {"watchlist_scan", "custom_pool_scan", "full_pool_local_scan"}
QUANT_PROJECTION_SCAN_MODE = "search_quant_projection"
QUANT_PROJECTION_SCHEMA_VERSION = "candidate_radar_search_quant_projection_receipt.v1"
QUANT_PROJECTION_ACTIVATION_SCHEMA_VERSION = "candidate_radar_search_quant_projection_activation_receipt.v1"
QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION = "candidate_radar_search_quant_projection_acceptance_dry_run.v1"
QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_TASK_TYPE = "run_candidate_radar_quant_projection_acceptance_dry_run"
QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_ROUTE = "POST /api/candidate-radar/quant-projection-acceptance-dry-run"
QUANT_PROJECTION_EXECUTION_REQUEST_SCHEMA_VERSION = "candidate_radar_search_quant_projection_execution_request.v1"
QUANT_PROJECTION_EXECUTION_REQUEST_TASK_TYPE = "run_candidate_radar_quant_projection_execution_request"
QUANT_PROJECTION_EXECUTION_REQUEST_ROUTE = "POST /api/candidate-radar/quant-projection-execution-request"
QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION = (
    "candidate_radar_search_quant_provider_model_acceptance.v1"
)
QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_TASK_TYPE = (
    "run_candidate_radar_quant_projection_provider_model_acceptance"
)
QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_ROUTE = (
    "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
)
QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS = ("trade_cal", "daily", "daily_basic", "moneyflow")
CANDIDATE_PROVIDER_PARITY_DRY_RUN_SCHEMA_VERSION = "candidate_radar_provider_parity_dry_run.v1"
CANDIDATE_PROVIDER_PARITY_DRY_RUN_TASK_TYPE = "run_candidate_radar_provider_parity_dry_run"
CANDIDATE_PROVIDER_PARITY_DRY_RUN_ROUTE = "POST /api/candidate-radar/provider-parity-dry-run"
CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_SCHEMA_VERSION = "candidate_radar_provider_parity_execution_request.v1"
CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_TASK_TYPE = "run_candidate_radar_provider_parity_execution_request"
CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_ROUTE = "POST /api/candidate-radar/provider-parity-execution-request"
CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_SCHEMA_VERSION = "candidate_radar_provider_parity_acceptance.v1"
CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_TASK_TYPE = "run_candidate_radar_provider_parity_acceptance"
CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_ROUTE = "POST /api/candidate-radar/provider-parity-acceptance"
PROVIDER_PARITY_ACCEPTANCE_API_ALIASES = {
    "holdertrade": "stk_holdertrade",
    "pledge": "pledge_stat",
}
PROVIDER_PARITY_ACCEPTANCE_LIGHT_APIS = (
    "moneyflow",
    "top_list",
    "top_inst",
    "anns_d",
)
PROVIDER_PARITY_DEFAULT_CANDIDATE_LIMIT = 20
CANDIDATE_WORKER_EXECUTION_REQUEST_SCHEMA_VERSION = "candidate_radar_worker_execution_request.v1"
CANDIDATE_WORKER_EXECUTION_REQUEST_TASK_TYPE = "run_candidate_radar_worker_execution_request"
CANDIDATE_WORKER_EXECUTION_REQUEST_ROUTE = "POST /api/candidate-radar/worker-execution-request"
CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION = "candidate_radar_full_pool_worker_fallback.v1"
CANDIDATE_FULL_POOL_WORKER_FALLBACK_TASK_TYPE = "run_candidate_radar_full_pool_worker_fallback"
CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE = "POST /api/candidate-radar/full-pool-worker-scan"
CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION = "candidate_radar_deep_scan_worker_fallback.v1"
CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_TASK_TYPE = "run_candidate_radar_deep_scan_worker_fallback"
CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE = "POST /api/candidate-radar/deep-scan-worker"
CANDIDATE_WORKER_RUNTIME_LINKED_EVIDENCE_SCHEMA_VERSION = "candidate_radar_worker_runtime_linked_evidence.v1"
WORKER_RUNTIME_QA_EXECUTION_PACKET_KEY = "command_center_3_worker_runtime_qa_execution_packet"
WORKER_RUNTIME_QA_EXECUTION_SCHEMA_VERSION = "worker_runtime_qa_execution_receipt.v1"
CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_SCHEMA_VERSION = "candidate_radar_production_replacement_review.v1"
CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_TASK_TYPE = "run_candidate_radar_production_replacement_review"
CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_ROUTE = "POST /api/candidate-radar/production-replacement-review"
CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION = "candidate_radar_production_promotion_dry_run.v1"
CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_TASK_TYPE = "run_candidate_radar_production_promotion_dry_run"
CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_ROUTE = "POST /api/candidate-radar/production-promotion-dry-run"
CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION = "candidate_radar_production_promotion_review.v1"
CANDIDATE_PRODUCTION_PROMOTION_REVIEW_TASK_TYPE = "run_candidate_radar_production_promotion_review"
CANDIDATE_PRODUCTION_PROMOTION_REVIEW_ROUTE = "POST /api/candidate-radar/production-promotion-review"
CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION = "candidate_radar_legacy_retirement_review.v1"
CANDIDATE_LEGACY_RETIREMENT_REVIEW_TASK_TYPE = "run_candidate_radar_legacy_retirement_review"
CANDIDATE_LEGACY_RETIREMENT_REVIEW_ROUTE = "POST /api/candidate-radar/legacy-retirement-review"
CANDIDATE_RADAR_PERSISTED_RECEIPT_SPECS = (
    (
        "candidate_radar_worker_execution_request_receipt",
        "candidate_radar_worker_execution_request_rows",
        CANDIDATE_WORKER_EXECUTION_REQUEST_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_full_pool_worker_fallback_receipt",
        "candidate_radar_full_pool_worker_fallback_rows",
        CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_deep_scan_worker_fallback_receipt",
        "candidate_radar_deep_scan_worker_fallback_rows",
        CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_production_replacement_review_receipt",
        "candidate_radar_production_replacement_review_rows",
        CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_production_promotion_dry_run_receipt",
        "candidate_radar_production_promotion_dry_run_rows",
        CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_production_promotion_review_receipt",
        "candidate_radar_production_promotion_review_rows",
        CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
    ),
    (
        "candidate_radar_legacy_retirement_review_receipt",
        "candidate_radar_legacy_retirement_review_rows",
        CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION,
    ),
    (
        "search_quant_provider_model_acceptance_receipt",
        "search_quant_provider_model_acceptance_rows",
        QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION,
    ),
    (
        "provider_parity_acceptance_receipt",
        "provider_parity_acceptance_rows",
        CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_SCHEMA_VERSION,
    ),
)
CANDIDATE_RADAR_DURABLE_EVIDENCE_SCHEMA_VERSION = "candidate_radar_durable_evidence_recipe.v1"
CANDIDATE_RADAR_DURABLE_EVIDENCE_KEYS = (
    "cache_render_boundary_visible",
    "quick_scan_task_pipeline_visible",
    "legacy_parity_inventory_visible",
    "no_feature_loss_surface_visible",
    "result_delta_clarity_visible",
    "local_full_pool_receipt_visible",
    "local_deep_scan_review_visible",
    "worker_execution_recipe_visible",
    "worker_execution_request_visible",
    "provider_parity_scope_ticket_required",
    "quant_projection_scope_ticket_required",
    "quant_projection_execution_request_visible",
    "worker_full_pool_execution_evidence_required",
    "worker_deep_scan_execution_evidence_required",
    "provider_backed_parity_call_ledger_required",
    "browser_visual_performance_evidence_required",
    "deepseek_model_ledger_if_enabled_required",
    "legacy_retirement_review_required",
    "production_promotion_review_required",
    "no_trade_action_secret_boundary",
)
CANDIDATE_RADAR_DURABLE_EVIDENCE_LABELS = {
    "cache_render_boundary_visible": "Cache render stays read-only and scan-silent",
    "quick_scan_task_pipeline_visible": "Quick scan task pipeline is visible",
    "legacy_parity_inventory_visible": "Legacy radar parity inventory is visible",
    "no_feature_loss_surface_visible": "No-feature-loss local surface is visible",
    "result_delta_clarity_visible": "Result delta clarity is visible",
    "local_full_pool_receipt_visible": "Local full-pool receipt is visible",
    "local_deep_scan_review_visible": "Local deep-scan review receipt is visible",
    "worker_execution_recipe_visible": "Worker execution recipe is visible",
    "worker_execution_request_visible": "Worker execution request ticket is visible",
    "provider_parity_scope_ticket_required": "Provider parity scope ticket is required",
    "quant_projection_scope_ticket_required": "Search quant projection scope ticket is required",
    "quant_projection_execution_request_visible": "Search quant projection execution request is visible",
    "worker_full_pool_execution_evidence_required": "Worker full-pool execution evidence is required",
    "worker_deep_scan_execution_evidence_required": "Worker deep-scan execution evidence is required",
    "provider_backed_parity_call_ledger_required": "Provider-backed parity call ledger is required",
    "browser_visual_performance_evidence_required": "Browser visual/performance evidence is required",
    "deepseek_model_ledger_if_enabled_required": "DeepSeek model ledger is required when enabled",
    "legacy_retirement_review_required": "Legacy radar retirement review is required",
    "production_promotion_review_required": "Production promotion review is required",
    "no_trade_action_secret_boundary": "No trade/action/secret boundary is preserved",
}
CANDIDATE_RADAR_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION = "candidate_radar_production_stage_scope_manifest.v1"
CANDIDATE_RADAR_PRODUCTION_STAGE_KEYS = (
    "cache_render_boundary",
    "quick_scan_task_pipeline",
    "local_full_pool_execution_receipt",
    "local_deep_scan_review_receipt",
    "worker_runtime_round_trip_link",
    "worker_transport_round_trip_smoke",
    "local_worker_full_pool_fallback_receipt",
    "local_worker_deep_scan_fallback_receipt",
    "worker_full_pool_execution",
    "worker_deep_scan_execution",
    "provider_parity_acceptance",
    "search_quant_provider_model_acceptance",
    "browser_visual_performance_promotion",
    "legacy_retirement_review",
    "production_promotion_review",
)
CANDIDATE_RADAR_PRODUCTION_STAGE_LABELS = {
    "cache_render_boundary": "cache render stays read-only and scan-silent",
    "quick_scan_task_pipeline": "quick radar scan runs through explicit task pipeline",
    "local_full_pool_execution_receipt": "local full-pool-like receipt stays local evidence",
    "local_deep_scan_review_receipt": "local deep-scan review stays local evidence",
    "worker_runtime_round_trip_link": "local worker runtime round-trip evidence is linked",
    "worker_transport_round_trip_smoke": "Candidate Radar task round-trips through local worker transport",
    "local_worker_full_pool_fallback_receipt": "local full-pool worker-fallback execution receipt is visible",
    "local_worker_deep_scan_fallback_receipt": "local deep-scan worker-fallback execution receipt is visible",
    "worker_full_pool_execution": "worker-backed full-pool execution evidence is required",
    "worker_deep_scan_execution": "worker-backed deep-scan execution evidence is required",
    "provider_parity_acceptance": "provider-backed legacy signal parity is required",
    "search_quant_provider_model_acceptance": "searched-symbol provider/model projection evidence is required",
    "browser_visual_performance_promotion": "browser visual and performance promotion is required",
    "legacy_retirement_review": "legacy radar retirement review is required",
    "production_promotion_review": "production promotion review is required",
}
LOCAL_CANDIDATE_RADAR_STAGE_EVIDENCE_KEYS = {
    "cache_render_boundary",
    "quick_scan_task_pipeline",
    "local_full_pool_execution_receipt",
    "local_deep_scan_review_receipt",
    "worker_runtime_round_trip_link",
    "worker_transport_round_trip_smoke",
    "local_worker_full_pool_fallback_receipt",
    "local_worker_deep_scan_fallback_receipt",
}
CANDIDATE_TUSHARE_ACCEPTANCE_ENV_KEYS = ("TUSHARE_TOKEN",)
CANDIDATE_DEEPSEEK_ACCEPTANCE_ENV_KEYS = ("DEEPSEEK_API_KEY", "DEEPSEEK_TOKEN_1", "DEEPSEEK_TOKEN_2")
PERSISTED_TASK_SCAN_MODES = LOCAL_POOL_SCAN_MODES | {
    QUANT_PROJECTION_SCAN_MODE,
    "deep_scan_local_review",
    "provider_parity_dry_run",
    "provider_parity_execution_request",
    "worker_execution_request",
    "full_pool_worker_fallback",
    "deep_scan_worker_fallback",
    "quant_projection_execution_request",
    "quant_projection_provider_model_acceptance",
    "production_replacement_review",
    "production_promotion_dry_run",
}
FAST_SCAN_DISPLAY_CANDIDATE_LIMIT = 120
FAST_SCAN_LOCAL_POOL_INPUT_LIMIT = 50
FULL_POOL_LOCAL_INPUT_LIMIT = 500
FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD = 500
PRIORITY_EXPLANATION_LIMIT = 30
SAFE_LIST_LIMIT = 200
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
FULL_POOL_FILTER_DEFAULTS = {
    "exclude_st": True,
    "exclude_chinext": True,
    "exclude_star": True,
    "exclude_bj": True,
    "exclude_low_amount": True,
    "trend_up_only": True,
}
FULL_POOL_REQUIRED_STORAGE_DATASETS = ["daily", "daily_basic", "moneyflow", "trade_cal"]
LEGACY_RADAR_SIGNAL_GROUPS = [
    {
        "group": "radar_packet",
        "source_keys": ["radar_packet", "command_center_radar_packet"],
        "role": "legacy ranking packet and top candidate cache",
    },
    {
        "group": "next_ticket_candidates",
        "source_keys": ["next_ticket_candidates"],
        "role": "legacy executable candidate rows",
    },
    {
        "group": "candidate_execution_evidence_overview",
        "source_keys": ["candidate_execution_evidence_overview"],
        "role": "candidate evidence and execution readiness summary",
    },
    {
        "group": "next_ticket_evidence_recovery_actions",
        "source_keys": ["next_ticket_evidence_recovery_actions"],
        "role": "manual evidence recovery actions",
    },
    {
        "group": "old_workspace_packet_bridge",
        "source_keys": ["old_workspace_packet_bridge"],
        "role": "legacy packet bridge for parity checks",
    },
    {
        "group": "risk_alerts",
        "source_keys": ["risk_alerts"],
        "role": "candidate-level risk warnings and guardrails",
    },
]
LEGACY_RADAR_PARITY_ITEMS = [
    {
        "key": "top_watch_excluded_split",
        "label": "Top / Watch / Excluded 分层",
        "legacy_sources": ["command_center_radar_packet.top_candidates", "watch_candidates", "excluded_candidates"],
        "current_fields": ["candidate_rows", "excluded_candidates"],
        "target_state": "top/watch/excluded all mapped or missing_reported",
        "current_support": "mapped_from_cache",
    },
    {
        "key": "evidence_links",
        "label": "四类证据链",
        "legacy_sources": ["moneyflow", "dragon_tiger", "limit_emotion", "hard_risk"],
        "current_fields": ["evidence_chain_summary", "candidate_execution_evidence_overview", "evidence_recovery_actions"],
        "target_state": "moneyflow/dragon-tiger/limit-emotion/hard-risk gaps are visible",
        "current_support": "gap_reported",
    },
    {
        "key": "scoring_dimensions",
        "label": "规则评分维度",
        "legacy_sources": ["trend_score", "money_score", "risk_score", "position_score", "information_score", "total_score"],
        "current_fields": ["score"],
        "target_state": "dimension scores preserved when present; missing dimensions are not invented",
        "current_support": "partial_cache_projection",
    },
    {
        "key": "trigger_invalidation",
        "label": "触发 / 失效条件",
        "legacy_sources": ["trigger_conditions", "invalid_conditions", "trigger_condition", "invalidation_condition"],
        "current_fields": ["trigger_condition", "invalidation_condition"],
        "target_state": "candidate rows keep trigger/invalidation text before action review",
        "current_support": "mapped_from_cache",
    },
    {
        "key": "holding_comparison",
        "label": "当前持仓对比",
        "legacy_sources": ["current_holding_context", "position_profile", "candidate_vs_holding_*", "switch_relation"],
        "current_fields": ["position_risk_budget", "holding_action", "position_context"],
        "target_state": "candidate-vs-holding comparison becomes explicit before replacing legacy fallback",
        "current_support": "missing_reported",
    },
    {
        "key": "candidate_pool_sources",
        "label": "候选池来源",
        "legacy_sources": ["manual_input", "TECH_SAMPLE_POOL", "watchlist", "A-share broad scan", "index pool", "mixed scan"],
        "current_fields": ["radar_packet.source", "candidate_rows.source"],
        "target_state": "quick/watchlist/custom/full-pool modes report universe and degraded mode",
        "current_support": "quick_cache_only",
    },
    {
        "key": "scan_filters",
        "label": "扫描过滤条件",
        "legacy_sources": ["exclude_st", "exclude_chinext", "exclude_star", "exclude_bj", "exclude_low_amount", "trend_up_only"],
        "current_fields": ["scan_coverage.skipped_reason_rows"],
        "target_state": "filters become task params and skipped_reason_rows before broad scan",
        "current_support": "future_task_required",
    },
    {
        "key": "timeout_and_fallback",
        "label": "超时 / 上次成功缓存回退",
        "legacy_sources": ["timeout_seconds", "previous_rows", "radar_scan_status"],
        "current_fields": ["sqlite_meta persisted packet", "task status"],
        "target_state": "last successful packet remains visible while new scan runs or fails",
        "current_support": "mapped_from_sqlite_cache",
    },
    {
        "key": "manual_deep_research",
        "label": "手动深度研究",
        "legacy_sources": ["call_deepseek_non_stream", "deep_research_results"],
        "current_fields": ["future manual DeepSeek task"],
        "target_state": "DeepSeek remains manual/button-gated and does not feed radar action",
        "current_support": "not_in_quick_scan",
    },
]
LEGACY_RADAR_OUTPUT_CONTRACT_FIELDS = [
    {"field": "status", "role": "radar packet state", "required_for": "cache display"},
    {"field": "source", "role": "candidate source label", "required_for": "coverage audit"},
    {"field": "generated_at", "role": "last successful packet timestamp", "required_for": "cache freshness"},
    {"field": "total_count", "role": "legacy scanned/result count", "required_for": "universe coverage"},
    {"field": "top_candidates", "role": "primary Top candidates", "required_for": "next-ticket display"},
    {"field": "watch_candidates", "role": "observe-only candidates", "required_for": "non-actionable visibility"},
    {"field": "excluded_candidates", "role": "blocked/excluded candidates", "required_for": "feature parity"},
    {"field": "decision_summary", "role": "execution-layer summary", "required_for": "manual review"},
    {"field": "evidence_items", "role": "score/status/trigger/invalid/data-gap evidence cards", "required_for": "audit"},
    {"field": "trigger_condition", "role": "candidate trigger text", "required_for": "no blind action"},
    {"field": "invalidation_condition", "role": "candidate invalidation text", "required_for": "risk boundary"},
    {"field": "data_gaps", "role": "missing evidence list", "required_for": "coverage gaps"},
]
SCAN_MODE_STATUS_ROWS = [
    {
        "scan_mode": "quick_cache_scan",
        "status": "implemented_cache_only",
        "scope": "local snapshot/cache candidate packet",
        "external_calls": False,
        "notes": "Current 3.0 button task writes SQLite packet and reports coverage gaps.",
    },
    {
        "scan_mode": "watchlist_scan",
        "status": "implemented_local_input",
        "scope": "local payload or snapshot watchlist",
        "external_calls": False,
        "notes": "Reads only provided/local watchlist candidates; missing watchlist is reported as a gap.",
    },
    {
        "scan_mode": "custom_pool_scan",
        "status": "implemented_local_input",
        "scope": "manual/custom candidate pool",
        "external_calls": False,
        "notes": "Parses local manual candidates, de-duplicates them, and keeps all results research-only.",
    },
    {
        "scan_mode": "full_pool_scan",
        "status": "planned_future_task_read_plan_available",
        "scope": "A-share broad/index pool scan",
        "external_calls": "button_gated_future",
        "notes": "Full-pool plan can be generated locally; actual scan still requires future worker execution and explicit provider refresh tasks.",
    },
    {
        "scan_mode": "full_pool_local_scan",
        "status": "implemented_local_universe_receipt",
        "scope": "explicit local universe payload/cache execution",
        "external_calls": False,
        "notes": "Consumes a local universe payload or cached candidates and writes a local execution receipt; it is not provider-backed full-market production acceptance.",
    },
    {
        "scan_mode": "full_pool_worker_fallback",
        "status": "implemented_local_worker_fallback_worker_runtime_pending",
        "scope": "explicit worker-shaped local full-pool fallback task",
        "external_calls": False,
        "notes": "Consumes local universe rows through the future worker route shape and writes a fallback receipt; Celery/Redis worker-backed production execution remains pending.",
    },
    {
        "scan_mode": "deep_scan",
        "status": "implemented_plan_only",
        "scope": "legacy parity, provider, freshness, worker, and action-boundary readiness",
        "external_calls": False,
        "notes": "Deep-scan plan is a local readiness checklist; it does not scan, refresh providers, score candidates, or call DeepSeek.",
    },
    {
        "scan_mode": "deep_scan_local_review",
        "status": "implemented_local_review_receipt",
        "scope": "local candidate evidence/parity/provider/freshness review",
        "external_calls": False,
        "notes": "Reviews local candidate evidence and gaps without DeepSeek/provider calls; production deep_scan remains pending.",
    },
    {
        "scan_mode": "search_quant_projection",
        "status": "implemented_local_receipt_provider_model_pending",
        "scope": "single searched symbol / bounded watchlist quant projection",
        "external_calls": False,
        "notes": "Validates a searched symbol, writes local projection receipt, and lists Tushare/Factor/Next Session/DeepSeek/ECharts gaps without calling providers or models.",
    },
    {
        "scan_mode": "provider_parity_dry_run",
        "status": "implemented_local_preflight_provider_model_pending",
        "scope": "bounded candidate radar provider parity acceptance ticket",
        "external_calls": False,
        "notes": "Binds future radar parity acceptance to selected candidate symbols, provider signal groups, safe credential presence, worker/browser evidence, and no-trade boundaries without calling providers or models.",
    },
    {
        "scan_mode": "manual_deep_research",
        "status": "planned_manual_only",
        "scope": "DeepSeek explanation for selected candidate",
        "external_calls": "button_gated_future",
        "notes": "Not part of quick scan; output must remain research-only.",
    },
]
RADAR_PROVIDER_SIGNAL_REQUIREMENTS = [
    {
        "signal_group": "moneyflow",
        "label": "资金流",
        "apis": ["moneyflow"],
        "legacy_role": "candidate fund-flow confirmation",
    },
    {
        "signal_group": "dragon_tiger",
        "label": "龙虎榜",
        "apis": ["top_list", "top_inst"],
        "legacy_role": "hot-money and institutional behavior",
    },
    {
        "signal_group": "limit_emotion",
        "label": "涨跌停/情绪",
        "apis": ["stk_limit", "limit_list_d", "limit_cpt_list"],
        "legacy_role": "limit-up/down and market emotion",
    },
    {
        "signal_group": "chip_radar",
        "label": "筹码/胜率",
        "apis": ["cyq_perf", "cyq_chips"],
        "legacy_role": "chip distribution and winner-rate pressure",
    },
    {
        "signal_group": "hard_risk",
        "label": "硬风险",
        "apis": ["anns_d", "forecast", "pledge", "holdertrade", "share_float", "stk_surv"],
        "legacy_role": "announcement and structural risk exclusion",
    },
]
PROVIDER_BLOCKED_MARKERS = {
    "blocked",
    "permission_denied",
    "not_configured",
    "disabled_this_session",
    "runtime_secret_missing",
    "requires_manual_config",
    "权限不足",
    "未配置",
    "本会话跳过",
}
PROVIDER_STALE_MARKERS = {"stale", "stale_cache", "expired", "historical", "fallback_used", "使用缓存", "过期"}
PROVIDER_MISSING_MARKERS = {
    "missing",
    "empty_recent",
    "not_loaded",
    "no_data",
    "cache_missing",
    "matrix_only",
    "近期无数据",
    "缺失",
}
PROVIDER_AVAILABLE_MARKERS = {"available", "ready", "success", "validated", "可用", "完成"}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=80): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:SAFE_LIST_LIMIT]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:SAFE_LIST_LIMIT]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "candidate_radar_cache_not_json_serializable"}


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _preserve_candidate_radar_persisted_receipts(
    packet: Mapping[str, Any],
    previous_packet: Mapping[str, Any],
) -> dict[str, Any]:
    view = dict(packet)
    for receipt_key, rows_key, schema_version in CANDIDATE_RADAR_PERSISTED_RECEIPT_SPECS:
        if isinstance(view.get(receipt_key), dict):
            continue
        previous_receipt = _as_dict(previous_packet.get(receipt_key))
        if previous_receipt.get("schema_version") != schema_version:
            continue
        view[receipt_key] = previous_receipt
        previous_rows = [row for row in _as_list(previous_packet.get(rows_key)) if isinstance(row, dict)]
        if not previous_rows:
            previous_rows = [row for row in _as_list(previous_receipt.get("rows")) if isinstance(row, dict)]
        view[rows_key] = previous_rows
    return view


def _first_non_empty(mapping: Mapping[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _split_candidate_text(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"[\s,，;；]+", value) if part.strip()]


def _candidate_code_from_item(item: Mapping[str, Any]) -> str:
    value = _first_non_empty(item, ["ticker", "ts_code", "code", "stock_code", "symbol"])
    return _safe_text(value, limit=32).upper()


def _candidate_name_from_item(item: Mapping[str, Any]) -> str:
    value = _first_non_empty(item, ["name", "stock_name", "security_name", "display_name"])
    return _safe_text(value, limit=80)


def _local_pool_items_from_payload(payload_safe: Mapping[str, Any], scan_mode: str) -> tuple[list[Any], str]:
    if scan_mode == "watchlist_scan":
        keys = ["watchlist_candidates", "watchlist_targets", "candidates", "targets"]
    elif scan_mode == "full_pool_local_scan":
        keys = [
            "full_pool_candidates",
            "universe_candidates",
            "local_universe_candidates",
            "local_universe",
            "candidates",
            "targets",
        ]
    else:
        keys = ["custom_candidates", "custom_pool", "manual_candidates", "candidates", "targets"]
    rows: list[Any] = []
    source_key = ""
    for key in keys:
        value = payload_safe.get(key)
        if value in (None, "", [], {}):
            continue
        source_key = f"payload.{key}"
        if isinstance(value, str):
            rows.extend(_split_candidate_text(value))
        elif isinstance(value, list):
            rows.extend(value)
        else:
            rows.append(value)
        break
    if scan_mode == "custom_pool_scan":
        text_value = payload_safe.get("custom_pool_text")
    elif scan_mode == "full_pool_local_scan":
        text_value = payload_safe.get("full_pool_text") or payload_safe.get("local_universe_text")
    else:
        text_value = payload_safe.get("watchlist_text")
    text_rows = _split_candidate_text(text_value)
    if text_rows and not rows:
        rows.extend(text_rows)
        if scan_mode == "custom_pool_scan":
            source_key = "payload.custom_pool_text"
        elif scan_mode == "full_pool_local_scan":
            source_key = "payload.full_pool_text"
        else:
            source_key = "payload.watchlist_text"
    return rows, source_key


def _local_watchlist_items_from_snapshot(snapshot_map: Mapping[str, Any]) -> tuple[list[Any], str]:
    for key in [
        "announcement_watchlist",
        "announcement_watchlist_payload",
        "watchlist",
        "watchlist_payload",
        "next_observation_targets",
        "watchlist_targets",
    ]:
        value = snapshot_map.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, Mapping):
            for child_key in ["targets", "items", "candidates", "rows"]:
                rows = value.get(child_key)
                if isinstance(rows, list):
                    return rows, f"snapshot.{key}.{child_key}"
        if isinstance(value, list):
            return value, f"snapshot.{key}"
    return [], ""


def _normalize_local_pool_candidates(
    raw_items: list[Any],
    *,
    scan_mode: str,
    input_source: str,
    max_items: int = FAST_SCAN_LOCAL_POOL_INPUT_LIMIT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    disabled_count = 0
    invalid_count = 0
    duplicate_count = 0
    truncated_count = max(0, len(raw_items) - max_items)
    if scan_mode == "watchlist_scan":
        source_label = "持续调查池本地输入"
    elif scan_mode == "full_pool_local_scan":
        source_label = "本地 full-pool universe 输入"
    else:
        source_label = "自定义候选池本地输入"

    for index, raw in enumerate(raw_items[:max_items], start=1):
        safe_raw = _safe_value(raw)
        item = safe_raw if isinstance(safe_raw, dict) else {"ticker": safe_raw}
        enabled = item.get("enabled", True)
        if enabled is False or str(enabled).strip().lower() in {"false", "0", "no", "disabled"}:
            disabled_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_disabled",
                    "group": scan_mode,
                    "severity": "info",
                    "row_index": index,
                    "ticker": _candidate_code_from_item(item),
                    "action": "skip_disabled_candidate_no_external_call",
                }
            )
            continue
        ticker = _candidate_code_from_item(item)
        if not ticker:
            invalid_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_missing_code",
                    "group": scan_mode,
                    "severity": "input_gap",
                    "row_index": index,
                    "action": "skip_invalid_candidate_do_not_guess_code",
                }
            )
            continue
        if ticker in seen:
            duplicate_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_duplicate",
                    "group": scan_mode,
                    "severity": "dedupe",
                    "row_index": index,
                    "ticker": ticker,
                    "action": "dedupe_local_candidate_keep_first",
                }
            )
            continue
        seen.add(ticker)
        candidates.append(
            {
                "rank": len(candidates) + 1,
                "ticker": ticker,
                "name": _candidate_name_from_item(item),
                "score": item.get("score"),
                "status_label": item.get("status_label") or "本地候选待验证",
                "action_state": item.get("action_state") or "只观察",
                "tone": item.get("tone") or "warn",
                "evidence_chain_summary": item.get("evidence_chain_summary") or "本地候选池输入；未刷新外部证据链。",
                "trigger_condition": item.get("trigger_condition") or item.get("trigger") or "",
                "invalidation_condition": item.get("invalidation_condition") or item.get("invalid_condition") or "",
                "source": item.get("source") or source_label,
                "updated_at": item.get("updated_at") or item.get("created_at"),
                "data_gaps": item.get("data_gaps")
                or ["local_pool_evidence_not_refreshed", "freshness_requires_current_cache_review"],
            }
        )

    if truncated_count:
        skipped.append(
            {
                "reason": "local_pool_candidate_limit_truncated",
                "group": scan_mode,
                "severity": "input_limit",
                "row_count": truncated_count,
                "action": "truncate_large_local_payload_keep_scan_fast",
            }
        )

    audit = {
        "scan_mode": scan_mode,
        "input_source": input_source or "missing",
        "input_candidate_count": len(raw_items),
        "normalized_candidate_count": len(candidates),
        "disabled_candidate_count": disabled_count,
        "invalid_candidate_count": invalid_count,
        "duplicate_candidate_count": duplicate_count,
        "truncated_candidate_count": truncated_count,
        "skipped_candidate_count": disabled_count + invalid_count + duplicate_count + truncated_count,
        "max_local_candidates": max_items,
        "sync_input_limit": max_items,
        "requires_worker_when_over_limit": truncated_count > 0,
        "cache_only": True,
        "external_calls_triggered": False,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_scan_full_market": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }
    return candidates, skipped, audit


def _snapshot_with_local_candidate_pool(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    scan_mode: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    raw_items, input_source = _local_pool_items_from_payload(payload_safe, scan_mode)
    if scan_mode == "watchlist_scan" and not raw_items:
        raw_items, input_source = _local_watchlist_items_from_snapshot(snapshot_map)
    if scan_mode == "full_pool_local_scan" and not raw_items:
        radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
        raw_items = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
        input_source = "snapshot.next_ticket_candidates_or_radar_top_candidates" if raw_items else input_source
    max_items = FULL_POOL_LOCAL_INPUT_LIMIT if scan_mode == "full_pool_local_scan" else FAST_SCAN_LOCAL_POOL_INPUT_LIMIT
    candidates, skipped, audit = _normalize_local_pool_candidates(
        raw_items,
        scan_mode=scan_mode,
        input_source=input_source,
        max_items=max_items,
    )
    overlay = dict(snapshot_map)
    existing_radar = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    if scan_mode == "watchlist_scan":
        source_text = "持续调查池本地扫描"
    elif scan_mode == "full_pool_local_scan":
        source_text = "本地 full-pool universe 执行"
    else:
        source_text = "自定义候选池本地扫描"
    overlay["next_ticket_candidates"] = candidates
    overlay["radar_packet"] = {
        **existing_radar,
        "status": "ready" if candidates else "cache_missing",
        "source": source_text,
        "summary": f"{source_text}生成 {len(candidates)} 个候选；未调用外部源，结果只用于 research-only 复核。",
        "generated_at": _now_iso(),
        "total_count": len(candidates),
        "top_candidates": candidates,
        "watch_candidates": [],
        "excluded_candidates": _as_list(existing_radar.get("excluded_candidates")),
        "manual_required_text": "本地候选池扫描不是买入指令；必须补齐证据链、freshness、纪律和仓位预算。",
    }
    overlay["local_candidate_pool_audit"] = audit
    overlay["local_candidate_pool_skipped_rows"] = skipped
    return overlay, audit, skipped


def _normalize_projection_symbol(payload_safe: Mapping[str, Any]) -> dict[str, Any]:
    raw_input = _first_non_empty(
        payload_safe,
        ["ts_code", "symbol", "ticker", "stock_code", "search_symbol", "query"],
    )
    raw_text = _safe_text(raw_input, limit=40).upper()
    compact = re.sub(r"[^0-9A-Z.]", "", raw_text)
    normalized = compact
    suffix_inferred = False
    status = "invalid_symbol"
    valid = False
    if re.fullmatch(r"\d{6}\.(SZ|SH|BJ)", compact):
        valid = True
        status = "valid"
    elif re.fullmatch(r"\d{6}", compact):
        if compact.startswith(("0", "3")):
            normalized = f"{compact}.SZ"
            suffix_inferred = True
            valid = True
            status = "valid_suffix_inferred"
        elif compact.startswith("6"):
            normalized = f"{compact}.SH"
            suffix_inferred = True
            valid = True
            status = "valid_suffix_inferred"
        elif compact.startswith(("4", "8")):
            normalized = f"{compact}.BJ"
            suffix_inferred = True
            valid = True
            status = "valid_suffix_inferred"
    return {
        "raw_input_safe": raw_text,
        "normalized_symbol": normalized if valid else "",
        "symbol_valid": valid,
        "symbol_status": status,
        "suffix_inferred": suffix_inferred,
        "validation_rule": "six_digit_a_share_with_SZ_SH_BJ_suffix_or_inferable_prefix",
        "contains_secret": False,
    }


def _quant_projection_row(
    step_key: str,
    status: str,
    evidence: str,
    *,
    local_ready: bool,
    production_blocker: bool,
) -> dict[str, Any]:
    return {
        "schema_version": QUANT_PROJECTION_SCHEMA_VERSION,
        "step_key": step_key,
        "status": status,
        "local_ready": bool(local_ready),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _build_quant_projection_receipt(
    *,
    symbol_info: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    candidate_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    symbol_valid = symbol_info.get("symbol_valid") is True
    rows = [
        _quant_projection_row(
            "symbol_validation",
            "passed" if symbol_valid else "blocked_invalid_symbol",
            f"raw={symbol_info.get('raw_input_safe')}; normalized={symbol_info.get('normalized_symbol')}; status={symbol_info.get('symbol_status')}",
            local_ready=symbol_valid,
            production_blocker=not symbol_valid,
        ),
        _quant_projection_row(
            "task_boundary",
            "passed_local_post_task",
            "Projection is created only by explicit POST task; GET cache and render stay read-only.",
            local_ready=True,
            production_blocker=False,
        ),
        _quant_projection_row(
            "tushare_light_refresh_pending",
            "pending_provider_execution",
            "Future real projection needs trade_cal if needed plus daily / daily_basic / moneyflow call ledger.",
            local_ready=False,
            production_blocker=True,
        ),
        _quant_projection_row(
            "factor_next_session_cache_pending",
            "pending_local_pipeline_after_provider",
            "Future projection should refresh Factor Quant Hub, Next Session cache, and ECharts payload after provider evidence is ready.",
            local_ready=False,
            production_blocker=True,
        ),
        _quant_projection_row(
            "deepseek_pro_explanation_pending",
            "pending_model_execution_optional",
            "Optional DeepSeek pro explanation requires model ledger, input/output hashes, sanitizer, and parse-failed discard.",
            local_ready=False,
            production_blocker=True,
        ),
        _quant_projection_row(
            "evidence_gap_display",
            "passed_gaps_visible",
            "Provider/freshness/model/chart gaps are shown as research gaps instead of hidden or converted to trade action.",
            local_ready=True,
            production_blocker=False,
        ),
        _quant_projection_row(
            "full_pool_deep_scan_boundary",
            "passed_not_started_on_search",
            "Search projection does not start full-pool or deep-scan execution.",
            local_ready=True,
            production_blocker=False,
        ),
        _quant_projection_row(
            "trade_action_isolation",
            "passed_research_only",
            "Projection cannot execute trades, modify holdings, or mutate strategy action.",
            local_ready=True,
            production_blocker=False,
        ),
    ]
    production_blockers = [row for row in rows if row.get("production_blocker") is True]
    receipt = {
        "schema_version": QUANT_PROJECTION_SCHEMA_VERSION,
        "status": "quant_projection_local_receipt_ready_provider_model_pending"
        if symbol_valid
        else "quant_projection_blocked_invalid_symbol",
        "scope": "local_search_to_quant_projection_no_provider_or_model_execution",
        "task_type": "run_candidate_radar_quant_projection",
        "scan_mode": QUANT_PROJECTION_SCAN_MODE,
        "symbol": symbol_info.get("normalized_symbol"),
        "raw_input_safe": symbol_info.get("raw_input_safe"),
        "symbol_valid": symbol_valid,
        "symbol_status": symbol_info.get("symbol_status"),
        "suffix_inferred": symbol_info.get("suffix_inferred"),
        "button_label": "生成 3.0 量化推演",
        "candidate_count": int(candidate_count),
        "selected_light_apis": ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"],
        "allowed_next_step": "run_user_approved_live_light_provider_model_acceptance_then_refresh_projection"
        if symbol_valid
        else "enter_valid_a_share_symbol_then_retry_projection",
        "missing_evidence_items": [
            "real Tushare light call ledger",
            "Factor Quant Hub refresh evidence",
            "Next Session/ECharts cache refresh evidence",
            "optional DeepSeek pro model ledger",
            "freshness expected_trade_date evidence",
        ],
        "not_allowed_next_steps": [
            "call Tushare from React render",
            "call DeepSeek from React render",
            "start full-pool or deep-scan from search render",
            "treat local projection receipt as buy/sell recommendation",
            "mutate strategy action or holdings",
        ],
        "local_receipt_ready": True,
        "ready_for_real_provider_model_projection": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "browser_nonblocking_evidence_complete": False,
        "production_quant_projection_complete": False,
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "call_ledger": [
            {
                "api": "local_candidate_radar_quant_projection_receipt",
                "source_snapshot": "local_search_payload",
                "request_params_safe": {
                    "symbol": symbol_info.get("normalized_symbol"),
                    "symbol_valid": symbol_valid,
                    "include_tushare": payload_safe.get("include_tushare") is True,
                    "include_deepseek": payload_safe.get("include_deepseek") is True,
                    "scan_mode": QUANT_PROJECTION_SCAN_MODE,
                },
                "row_count": len(rows),
                "call_status": "local_quant_projection_receipt_ready_no_external_call"
                if symbol_valid
                else "local_quant_projection_blocked_invalid_symbol_no_external_call",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }
    return receipt, rows


def _quant_projection_activation_row(
    activation_key: str,
    status: str,
    evidence: str,
    next_action: str,
    *,
    passed: bool,
    production_blocker: bool,
) -> dict[str, Any]:
    return {
        "schema_version": QUANT_PROJECTION_ACTIVATION_SCHEMA_VERSION,
        "activation_key": activation_key,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _quant_projection_activation_receipt(
    quant_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _as_dict(quant_receipt)
    if not receipt:
        return {}, []
    schema_ok = receipt.get("schema_version") == QUANT_PROJECTION_SCHEMA_VERSION
    symbol_valid = receipt.get("symbol_valid") is True
    selected_apis = _as_list(receipt.get("selected_light_apis"))
    rows = [
        _quant_projection_activation_row(
            "local_receipt_visible",
            "passed" if schema_ok else "missing",
            f"receipt_schema={receipt.get('schema_version') or 'missing'}; status={receipt.get('status') or 'missing'}",
            "Keep the local receipt visible before any provider/model task can run.",
            passed=schema_ok,
            production_blocker=not schema_ok,
        ),
        _quant_projection_activation_row(
            "symbol_validation_ready",
            "passed" if symbol_valid else "blocked_invalid_symbol",
            f"symbol={receipt.get('symbol') or '--'}; symbol_status={receipt.get('symbol_status') or 'unknown'}",
            "Enter a valid A-share symbol before requesting real provider/model projection.",
            passed=symbol_valid,
            production_blocker=not symbol_valid,
        ),
        _quant_projection_activation_row(
            "explicit_real_provider_task_required",
            "pending_explicit_task",
            "A separate user-approved provider/model task must execute real projection; the local receipt is not execution.",
            "Create a future explicit POST task that binds to the receipt scope and writes real call/model ledger evidence.",
            passed=False,
            production_blocker=True,
        ),
        _quant_projection_activation_row(
            "tushare_light_call_ledger_required",
            "pending_provider_call_ledger",
            f"selected_light_apis={selected_apis}; current_tushare_called={receipt.get('tushare_called') is True}",
            "Record real Tushare trade_cal-if-needed, daily, daily_basic, and moneyflow rows with safe request params and call_status.",
            passed=False,
            production_blocker=True,
        ),
        _quant_projection_activation_row(
            "factor_next_session_refresh_required",
            "pending_local_pipeline_after_provider",
            f"factor_refresh_executed={receipt.get('factor_refresh_executed') is True}; next_session_refresh_executed={receipt.get('next_session_refresh_executed') is True}; echarts_payload_refreshed={receipt.get('echarts_payload_refreshed') is True}",
            "After provider evidence is ready, refresh Factor Quant Hub, Next Session cache, and ECharts payload through backend tasks.",
            passed=False,
            production_blocker=True,
        ),
        _quant_projection_activation_row(
            "deepseek_model_ledger_required",
            "pending_optional_model_ledger",
            f"model_execution_implemented={receipt.get('model_execution_implemented') is True}; current_deepseek_called={receipt.get('deepseek_called') is True}",
            "If DeepSeek pro explanation is enabled, record model_used, token usage, parse status, input/output hash, sanitizer result, and safe fallback.",
            passed=False,
            production_blocker=True,
        ),
        _quant_projection_activation_row(
            "browser_nonblocking_evidence_required",
            "pending_browser_nonblocking_evidence",
            f"browser_nonblocking_evidence_complete={receipt.get('browser_nonblocking_evidence_complete') is True}",
            "Prove the React page renders cached state first, then tracks the task without blocking or creating duplicate tasks.",
            passed=False,
            production_blocker=True,
        ),
        _quant_projection_activation_row(
            "full_pool_deep_scan_boundary_preserved",
            "passed",
            "Search projection does not start full-pool or deep-scan execution from render.",
            "Keep full-pool/deep-scan as separate explicit worker tasks.",
            passed=True,
            production_blocker=False,
        ),
        _quant_projection_activation_row(
            "trade_action_isolation_preserved",
            "passed",
            "Projection receipt cannot execute trades, mutate holdings, or modify strategy action.",
            "Keep quant projection output research-only until separate trade review exists.",
            passed=True,
            production_blocker=False,
        ),
        _quant_projection_activation_row(
            "production_promotion_review_required",
            "pending_promotion_review",
            "Provider/model/factor/chart/browser evidence must be reviewed before production completion flags change.",
            "Only promote after direct evidence exists and redaction/safety review passes.",
            passed=False,
            production_blocker=True,
        ),
    ]
    local_blockers = [row["activation_key"] for row in rows if not row.get("passed") and row["activation_key"] in {"local_receipt_visible", "symbol_validation_ready"}]
    production_blockers = [row["activation_key"] for row in rows if row.get("production_blocker")]
    activation_receipt = {
        "schema_version": QUANT_PROJECTION_ACTIVATION_SCHEMA_VERSION,
        "status": "quant_projection_activation_ready_provider_model_execution_blocked"
        if not local_blockers
        else "quant_projection_activation_blocked_local_receipt_or_symbol",
        "scope": "local_search_quant_projection_activation_receipt_no_provider_or_model_call",
        "ltg": "LTG-13/LTG-02/LTG-07",
        "symbol": receipt.get("symbol"),
        "local_activation_receipt_ready": not local_blockers,
        "ready_for_real_provider_model_projection": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "browser_nonblocking_evidence_complete": False,
        "production_quant_projection_complete": False,
        "allowed_next_step": "create_explicit_user_approved_quant_projection_provider_model_task_with_ledger"
        if not local_blockers
        else "fix_symbol_or_local_receipt_then_retry",
        "missing_evidence_items": [
            "explicit real provider/model task implementation",
            "real Tushare light call ledger",
            "Factor Quant Hub refresh evidence",
            "Next Session/ECharts refresh evidence",
            "optional DeepSeek pro model ledger",
            "browser non-blocking task evidence",
            "redaction and production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat local receipt as real provider execution",
            "call Tushare or DeepSeek from React render",
            "skip call_ledger or model_ledger evidence",
            "start full-pool or deep-scan from search render",
            "turn projection into buy/sell instruction",
            "mutate strategy action, price, holdings, or operation zones",
        ],
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This activation receipt organizes the next real search-quant projection acceptance path. It does not call providers/models and is not production completion.",
    }
    return activation_receipt, rows


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled", "approved"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "blocked"}:
        return False
    return bool(default)


def _selected_quant_acceptance_apis(payload_safe: Mapping[str, Any], *, include_tushare: bool) -> tuple[list[str], list[str]]:
    raw_apis = _as_list(payload_safe.get("selected_apis") or payload_safe.get("apis"))
    if not raw_apis:
        raw_apis = list(QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS)
    selected: list[str] = []
    ignored: list[str] = []
    for item in raw_apis[:SAFE_LIST_LIMIT]:
        api = _safe_text(item, limit=40).strip().lower()
        if api == "trade_cal_if_needed":
            api = "trade_cal"
        if api in QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS and include_tushare:
            if api not in selected:
                selected.append(api)
        elif api:
            ignored.append(api)
    if include_tushare and "trade_cal" not in selected:
        selected = ["trade_cal"] + selected
    return selected, ignored


def _quant_acceptance_credential_presence_rows(
    *,
    include_tushare: bool,
    include_deepseek: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs = [
        {
            "provider": "tushare",
            "required": include_tushare,
            "env_keys": CANDIDATE_TUSHARE_ACCEPTANCE_ENV_KEYS,
            "credential_refs": ["tushare_primary_credential"],
        },
        {
            "provider": "deepseek",
            "required": include_deepseek,
            "env_keys": CANDIDATE_DEEPSEEK_ACCEPTANCE_ENV_KEYS,
            "credential_refs": [
                "deepseek_primary_credential",
                "deepseek_secondary_credential_1",
                "deepseek_secondary_credential_2",
            ],
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        required = bool(spec["required"])
        present = any(key in os.environ for key in spec["env_keys"])
        status = "present_no_value_read" if present else "missing_no_value_read"
        if not required:
            status = "not_required_by_payload"
        rows.append(
            {
                "schema_version": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
                "provider": spec["provider"],
                "required": required,
                "present": bool(present and required),
                "status": status,
                "credential_refs": list(spec["credential_refs"]),
                "credential_ref_count": len(spec["credential_refs"]),
                "env_key_name_count": len(spec["env_keys"]),
                "env_key_names_included": False,
                "presence_check_method": "environment_key_membership_only_no_value_read",
                "values_read": False,
                "values_exposed": False,
                "value_lengths_exposed": False,
                "contains_secret": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    required_rows = [row for row in rows if row["required"]]
    missing_rows = [row for row in required_rows if not row["present"]]
    summary = {
        "schema_version": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "status": "all_required_env_keys_present_no_values_read"
        if not missing_rows
        else "required_env_key_missing_no_values_read",
        "required_provider_count": len(required_rows),
        "present_provider_count": len(required_rows) - len(missing_rows),
        "missing_provider_count": len(missing_rows),
        "presence_check_method": "environment_key_membership_only_no_value_read",
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "contains_secret": False,
    }
    return rows, summary


def _quant_acceptance_scope_ticket(
    *,
    symbol: str,
    selected_apis: list[str],
    ignored_apis: list[str],
    include_tushare: bool,
    include_deepseek: bool,
    user_approved: bool,
    credential_status: str,
) -> dict[str, Any]:
    scope_input = {
        "route": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_ROUTE,
        "task_type": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_TASK_TYPE,
        "symbol": symbol,
        "selected_apis": selected_apis,
        "ignored_apis": ignored_apis,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "user_approved": user_approved,
        "credential_presence_status": credential_status,
    }
    serialized = json.dumps(scope_input, ensure_ascii=False, sort_keys=True, default=str)
    scope_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "schema_version": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:16],
        "scope_hash_algorithm": "sha256",
        "scope_hash_input": scope_input,
        "credential_values_included": False,
        "env_key_names_included": False,
        "contains_secret": False,
    }


def _quant_projection_acceptance_row(
    criterion: str,
    status: str,
    evidence: str,
    next_action: str,
    *,
    passed: bool,
    blocks_real_execution: bool,
) -> dict[str, Any]:
    return {
        "schema_version": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_real_execution": bool(blocks_real_execution),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _build_quant_projection_acceptance_dry_run(
    *,
    quant_receipt: Mapping[str, Any],
    activation_receipt: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    receipt = _as_dict(quant_receipt)
    activation = _as_dict(activation_receipt)
    symbol = str(receipt.get("symbol") or "")
    symbol_valid = receipt.get("symbol_valid") is True
    include_tushare = _coerce_bool(payload_safe.get("include_tushare"), True)
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), True)
    user_approved = _coerce_bool(payload_safe.get("user_approved") or payload_safe.get("approved"), False)
    selected_apis, ignored_apis = _selected_quant_acceptance_apis(payload_safe, include_tushare=include_tushare)
    credential_rows, credential_summary = _quant_acceptance_credential_presence_rows(
        include_tushare=include_tushare,
        include_deepseek=include_deepseek,
    )
    missing_credentials = int(credential_summary.get("missing_provider_count") or 0)
    scope_ticket = _quant_acceptance_scope_ticket(
        symbol=symbol,
        selected_apis=selected_apis,
        ignored_apis=ignored_apis,
        include_tushare=include_tushare,
        include_deepseek=include_deepseek,
        user_approved=user_approved,
        credential_status=str(credential_summary.get("status") or "unknown"),
    )
    rows = [
        _quant_projection_acceptance_row(
            "activation_receipt_visible",
            "passed" if activation.get("local_activation_receipt_ready") is True else "blocked_missing_activation_receipt",
            f"activation_status={activation.get('status') or 'missing'}",
            "Run local quant projection first so activation receipt is visible.",
            passed=activation.get("local_activation_receipt_ready") is True,
            blocks_real_execution=activation.get("local_activation_receipt_ready") is not True,
        ),
        _quant_projection_acceptance_row(
            "explicit_user_approval_recorded",
            "passed_user_approved_dry_run" if user_approved else "blocked_user_approval_required",
            f"user_approved={user_approved}",
            "Require explicit user approval before any provider/model acceptance dry-run can become review-ready.",
            passed=user_approved,
            blocks_real_execution=not user_approved,
        ),
        _quant_projection_acceptance_row(
            "symbol_scope_bound",
            "passed" if symbol_valid else "blocked_invalid_symbol",
            f"symbol={symbol or '--'}; symbol_status={receipt.get('symbol_status') or 'unknown'}",
            "Bind the future provider/model run to one validated A-share symbol.",
            passed=symbol_valid,
            blocks_real_execution=not symbol_valid,
        ),
        _quant_projection_acceptance_row(
            "allowed_light_apis_only",
            "passed_allowed_scope" if not ignored_apis else "passed_ignored_disallowed_apis",
            f"selected_apis={selected_apis}; ignored_apis={ignored_apis}",
            "Keep real Tushare scope limited to trade_cal, daily, daily_basic, and moneyflow.",
            passed=True,
            blocks_real_execution=False,
        ),
        _quant_projection_acceptance_row(
            "server_credential_presence_checked",
            "passed_no_values_read" if not missing_credentials else "blocked_missing_server_credentials",
            f"credential_presence_status={credential_summary.get('status')}; missing={missing_credentials}",
            "Configure missing server-side credentials, then rerun dry-run; never expose credential values.",
            passed=not missing_credentials,
            blocks_real_execution=bool(missing_credentials),
        ),
        _quant_projection_acceptance_row(
            "tushare_call_ledger_required",
            "pending_real_provider_ledger",
            "Dry-run did not call Tushare; future real task must record safe call_ledger rows.",
            "Record provider, api, request_params_safe, row_count, data_date, local_fetched_at, call_status, and safe errors.",
            passed=False,
            blocks_real_execution=True,
        ),
        _quant_projection_acceptance_row(
            "deepseek_model_ledger_required",
            "pending_optional_model_ledger" if include_deepseek else "skipped_not_requested",
            "Dry-run did not call DeepSeek; optional model execution needs model ledger and sanitizer evidence.",
            "Record model_used, token usage, parse status, input/output hash, sanitizer result, and parse_failed discard.",
            passed=not include_deepseek,
            blocks_real_execution=include_deepseek,
        ),
        _quant_projection_acceptance_row(
            "factor_next_echarts_refresh_required",
            "pending_local_pipeline_after_provider",
            "Factor Quant Hub, Next Session cache, and ECharts payload were not refreshed by this dry-run.",
            "Refresh local research caches only after provider evidence is available.",
            passed=False,
            blocks_real_execution=True,
        ),
        _quant_projection_acceptance_row(
            "browser_nonblocking_evidence_required",
            "pending_browser_evidence",
            "Need evidence that React renders cache first and tracks the task without blocking or duplication.",
            "Run browser/runtime review after real task implementation exists.",
            passed=False,
            blocks_real_execution=True,
        ),
        _quant_projection_acceptance_row(
            "trade_action_isolation_preserved",
            "passed_research_only",
            "Dry-run cannot execute trades, mutate holdings, or modify strategy action.",
            "Keep search quant projection research-only.",
            passed=True,
            blocks_real_execution=False,
        ),
        _quant_projection_acceptance_row(
            "production_promotion_review_required",
            "pending_promotion_review",
            "Provider/model/cache/browser evidence still needs redaction and production promotion review.",
            "Promote only after direct evidence exists and push gate remains green.",
            passed=False,
            blocks_real_execution=True,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("blocks_real_execution")]
    if not symbol_valid:
        status = "quant_projection_acceptance_dry_run_blocked_invalid_symbol"
        allowed_next_step = "enter_valid_a_share_symbol_then_rerun_projection"
    elif not user_approved:
        status = "quant_projection_acceptance_dry_run_blocked_user_approval_required"
        allowed_next_step = "rerun_dry_run_with_explicit_user_approval"
    elif missing_credentials:
        status = "quant_projection_acceptance_dry_run_blocked_missing_credentials"
        allowed_next_step = "configure_server_credentials_then_rerun_dry_run"
    else:
        status = "quant_projection_acceptance_dry_run_ready_real_execution_still_blocked"
        allowed_next_step = "implement_explicit_real_provider_model_quant_projection_task_bound_to_scope_ticket"
    dry_run = {
        "schema_version": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "local_search_quant_projection_provider_model_acceptance_dry_run_no_provider_or_model_call",
        "task_type": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_TASK_TYPE,
        "route": QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_ROUTE,
        "symbol": symbol,
        "symbol_valid": symbol_valid,
        "user_approved": user_approved,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "selected_apis": selected_apis,
        "ignored_apis": ignored_apis,
        "credential_presence_summary": credential_summary,
        "credential_presence_rows": credential_rows,
        "acceptance_scope_ticket": scope_ticket,
        "acceptance_scope_hash": scope_ticket["scope_hash"],
        "acceptance_scope_hash_short": scope_ticket["scope_hash_short"],
        "local_dry_run_ready": symbol_valid,
        "ready_for_user_approved_real_acceptance": bool(symbol_valid and user_approved and not missing_credentials),
        "ready_to_execute_real_provider_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "browser_nonblocking_evidence_complete": False,
        "production_quant_projection_complete": False,
        "allowed_next_step": allowed_next_step,
        "missing_evidence_items": [
            "explicit real provider/model quant projection task implementation",
            "real Tushare light call ledger",
            "optional DeepSeek pro model ledger",
            "Factor Quant Hub refresh evidence",
            "Next Session/ECharts refresh evidence",
            "browser non-blocking task evidence",
            "redaction and production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat dry-run as real provider/model execution",
            "skip credential presence gate",
            "return env key names or credential values",
            "call Tushare or DeepSeek from React render",
            "promote dry-run to production quant projection",
            "turn projection into buy/sell instruction",
            "mutate strategy action, price, holdings, or operation zones",
        ],
        "row_count": len(rows),
        "blocking_phase_count": len(blocking_rows),
        "credential_missing_provider_count": missing_credentials,
        "credential_present_provider_count": credential_summary.get("present_provider_count", 0),
        "credential_required_provider_count": credential_summary.get("required_provider_count", 0),
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
    }
    return dry_run, rows, credential_rows


def _quant_projection_execution_request_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": QUANT_PROJECTION_EXECUTION_REQUEST_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_quant_projection_execution_request(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_request: bool = False,
    task_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = payload_safe or {}
    operator_approved = _coerce_bool(
        payload.get("operator_approved") or payload.get("user_approved") or payload.get("approved"),
        False,
    )
    dry_run = _as_dict(packet.get("search_quant_projection_acceptance_dry_run_receipt"))
    requested_scope_hash = _safe_text(
        payload.get("acceptance_scope_hash") or payload.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(dry_run.get("acceptance_scope_hash") or "", limit=128)
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    dry_run_scope_visible = bool(expected_scope_hash)
    dry_run_ready = bool(
        dry_run_scope_visible
        and dry_run.get("symbol_valid") is True
        and dry_run.get("user_approved") is True
        and dry_run.get("local_dry_run_ready") is True
    )
    selected_apis = [str(api) for api in _as_list(dry_run.get("selected_apis"))]
    include_tushare = dry_run.get("include_tushare") is True
    include_deepseek = dry_run.get("include_deepseek") is True
    credential_missing = int(dry_run.get("credential_missing_provider_count") or 0)
    rows = [
        _quant_projection_execution_request_row(
            "explicit_post_quant_projection_execution_request_done",
            "passed_explicit_post" if explicit_request else "blocked_missing_explicit_post",
            passed=explicit_request,
            local_blocker=not explicit_request,
            production_blocker=False,
            evidence=f"explicit_request={explicit_request}; task_id={task_id or ''}",
            next_action="Use only POST /api/candidate-radar/quant-projection-execution-request to create the request ticket.",
        ),
        _quant_projection_execution_request_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_request and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before any future provider/model quant projection task.",
        ),
        _quant_projection_execution_request_row(
            "acceptance_dry_run_scope_ticket_visible",
            "passed_scope_ticket_visible" if dry_run_scope_visible else "blocked_acceptance_dry_run_missing",
            passed=dry_run_scope_visible,
            local_blocker=not dry_run_scope_visible,
            production_blocker=False,
            evidence=f"dry_run_status={dry_run.get('status') or 'missing'}; scope={dry_run.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Run the user-approved quant projection acceptance dry-run before requesting real execution.",
        ),
        _quant_projection_execution_request_row(
            "acceptance_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            local_blocker=explicit_request and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind the execution request to the latest quant projection acceptance dry-run scope hash.",
        ),
        _quant_projection_execution_request_row(
            "acceptance_dry_run_ready",
            "passed_dry_run_ready" if dry_run_ready else "blocked_dry_run_not_ready",
            passed=dry_run_ready,
            local_blocker=explicit_request and not dry_run_ready,
            production_blocker=False,
            evidence=(
                f"local_dry_run_ready={dry_run.get('local_dry_run_ready')}; "
                f"user_approved={dry_run.get('user_approved')}; "
                f"ready_for_user_approved_real_acceptance={dry_run.get('ready_for_user_approved_real_acceptance')}; "
                f"credential_missing_for_future_execution={credential_missing}"
            ),
            next_action="Resolve dry-run blockers before requesting a future provider/model task.",
        ),
        _quant_projection_execution_request_row(
            "selected_light_apis_bound",
            "passed_allowed_light_apis_bound" if selected_apis else "blocked_selected_apis_missing",
            passed=bool(selected_apis),
            local_blocker=explicit_request and not selected_apis,
            production_blocker=False,
            evidence=f"selected_apis={selected_apis}; allowed={list(QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS)}",
            next_action="Keep future provider execution limited to the approved light API scope.",
        ),
        _quant_projection_execution_request_row(
            "target_provider_model_route_declared",
            "passed_target_route_declared",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="future POST /api/candidate-radar/quant-projection-provider-model-acceptance",
            next_action="Implement the future real provider/model task only after this request is review-ready.",
        ),
        _quant_projection_execution_request_row(
            "provider_model_execution_still_pending",
            "passed_request_only",
            passed=True,
            local_blocker=False,
            production_blocker=True,
            evidence="Request ticket does not create or execute a provider/model task.",
            next_action="Keep real Tushare and optional DeepSeek execution as a separate explicit task with ledgers.",
        ),
        _quant_projection_execution_request_row(
            "factor_next_echarts_refresh_still_pending",
            "passed_refresh_pending",
            passed=True,
            local_blocker=False,
            production_blocker=True,
            evidence="Factor Quant Hub, Next Session, and ECharts cache refresh evidence remains pending.",
            next_action="Refresh local research caches only after real provider/model evidence exists.",
        ),
        _quant_projection_execution_request_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="No Tushare/DeepSeek/GitHub call, no task dispatch, no trade/action mutation, no secret exposure.",
            next_action="Preserve this boundary while adding future provider/model evidence.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    if not explicit_request:
        status = "quant_projection_execution_request_missing"
        allowed_next_step = "create_button_gated_quant_projection_execution_request"
    elif not operator_approved:
        status = "quant_projection_execution_request_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not dry_run_scope_visible:
        status = "quant_projection_execution_request_blocked_acceptance_dry_run_required"
        allowed_next_step = "run_quant_projection_acceptance_dry_run"
    elif not requested_scope_hash:
        status = "quant_projection_execution_request_blocked_scope_hash_required"
        allowed_next_step = "bind_latest_quant_projection_acceptance_scope_hash"
    elif not scope_hash_matches:
        status = "quant_projection_execution_request_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_quant_projection_acceptance_scope_hash"
    elif not dry_run_ready:
        status = "quant_projection_execution_request_blocked_dry_run_not_ready"
        allowed_next_step = "resolve_quant_projection_acceptance_dry_run_blockers"
    else:
        status = "quant_projection_execution_request_ready_manual_provider_model_task_pending"
        allowed_next_step = "manual_future_provider_model_task_implementation_with_call_and_model_ledgers"
    local_ready = explicit_request and operator_approved and not local_blockers
    receipt = {
        "schema_version": QUANT_PROJECTION_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_search_quant_projection_execution_request_no_provider_or_model_call",
        "mode": "button_gated_local_quant_projection_execution_request",
        "ltg": "LTG-13/LTG-02/LTG-07",
        "route": QUANT_PROJECTION_EXECUTION_REQUEST_ROUTE,
        "task_type": QUANT_PROJECTION_EXECUTION_REQUEST_TASK_TYPE,
        "request_task_id": task_id or "",
        "explicit_quant_projection_execution_request_done": explicit_request,
        "operator_approved": operator_approved,
        "local_execution_request_ready": local_ready,
        "ready_for_manual_provider_model_task_submission": local_ready,
        "acceptance_dry_run_scope_ticket_visible": dry_run_scope_visible,
        "acceptance_dry_run_ready": dry_run_ready,
        "acceptance_scope_hash": expected_scope_hash,
        "acceptance_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_acceptance_scope_hash": requested_scope_hash,
        "requested_acceptance_scope_hash_matches_latest": scope_hash_matches,
        "symbol": dry_run.get("symbol") or "",
        "symbol_valid": dry_run.get("symbol_valid") is True,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "selected_apis": selected_apis,
        "credential_missing_provider_count": credential_missing,
        "target_provider_model_route": "future POST /api/candidate-radar/quant-projection-provider-model-acceptance",
        "target_provider_model_task_type": "future_run_candidate_radar_quant_projection_provider_model_acceptance",
        "allowed_next_step": allowed_next_step,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "blocking_criteria": local_blockers,
        "production_blockers": production_blockers,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": False,
        "deepseek_model_ledger_evidence_done": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "browser_nonblocking_evidence_complete": False,
        "production_quant_projection_complete": False,
        "production_radar_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "not_allowed_next_steps": [
            "create provider/model task from execution request",
            "call Tushare/DeepSeek/GitHub from execution request",
            "refresh Factor/Next/ECharts from execution request",
            "treat execution request as real provider/model execution",
            "promote request to production quant projection",
            "turn projection into buy/sell instruction",
            "mutate strategy action, price, holdings, or operation zones",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "row_count": len(rows),
        "rows": rows,
        "note": "This local request ticket binds searched-symbol quant projection provider/model scope for a future task. It does not call Tushare, call DeepSeek, refresh research caches, execute trades, or complete production projection.",
    }
    return receipt, rows


def _attach_quant_projection_execution_request(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("search_quant_projection_execution_request_receipt"))
    if existing.get("schema_version") == QUANT_PROJECTION_EXECUTION_REQUEST_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("search_quant_projection_execution_request_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_quant_projection_execution_request(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["search_quant_projection_execution_request_row_count"] = len(rows)
    counts["search_quant_projection_execution_request_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["search_quant_projection_execution_request_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["search_quant_projection_execution_request_ready"] = receipt.get("local_execution_request_ready") is True
    policy = dict(_as_dict(view.get("policy")))
    policy["search_quant_projection_execution_request_is_button_gated"] = True
    policy["search_quant_projection_execution_request_is_local"] = True
    policy["search_quant_projection_execution_request_does_not_call_provider_or_model"] = True
    policy["search_quant_projection_execution_request_is_not_production_completion"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_quant_projection_execution_request",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "quant_projection_execution_request_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["search_quant_projection_execution_request_receipt"] = receipt
    view["search_quant_projection_execution_request_rows"] = rows
    return view


def _attach_provider_parity_execution_request(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("provider_parity_execution_request_receipt"))
    if existing.get("schema_version") == CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_SCHEMA_VERSION:
        receipt = dict(existing)
        acceptance_scope_hash = _safe_text(receipt.get("acceptance_scope_hash") or "", limit=128)
        requested_scope_hash = _safe_text(receipt.get("requested_acceptance_scope_hash") or "", limit=128)
        scope_matches = receipt.get("requested_acceptance_scope_hash_matches_latest") is True
        receipt.setdefault("provider_parity_scope_hash", acceptance_scope_hash)
        receipt.setdefault(
            "provider_parity_scope_hash_short",
            str(receipt.get("acceptance_scope_hash_short") or acceptance_scope_hash[:16]),
        )
        receipt.setdefault("requested_provider_parity_scope_hash", requested_scope_hash)
        receipt.setdefault("requested_provider_parity_scope_hash_matches_latest", scope_matches)
        rows = [
            row
            for row in _as_list(view.get("provider_parity_execution_request_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_provider_parity_execution_request(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["provider_parity_execution_request_row_count"] = len(rows)
    counts["provider_parity_execution_request_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["provider_parity_execution_request_production_blocker_count"] = receipt.get("production_blocker_count", 0)
    counts["provider_parity_execution_request_ready"] = receipt.get("local_execution_request_ready") is True
    policy = dict(_as_dict(view.get("policy")))
    policy["provider_parity_execution_request_is_button_gated"] = True
    policy["provider_parity_execution_request_is_local"] = True
    policy["provider_parity_execution_request_does_not_call_provider_or_model"] = True
    policy["provider_parity_execution_request_is_not_provider_backed_acceptance"] = True
    policy["provider_parity_execution_request_is_not_production_replacement"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_provider_parity_execution_request",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_provider_parity_execution_request_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["provider_parity_execution_request_receipt"] = receipt
    view["provider_parity_execution_request_rows"] = rows
    return view


def _candidate_provider_parity_selected_groups(payload_safe: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    allowed_groups = [str(requirement["signal_group"]) for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS]
    raw_groups = payload_safe.get("selected_signal_groups") or payload_safe.get("signal_groups") or allowed_groups
    if isinstance(raw_groups, str):
        raw_items = _split_candidate_text(raw_groups)
    elif isinstance(raw_groups, list):
        raw_items = [str(item or "").strip() for item in raw_groups]
    else:
        raw_items = allowed_groups

    selected: list[str] = []
    ignored: list[str] = []
    allowed_set = set(allowed_groups)
    for item in raw_items:
        group = str(item or "").strip().lower()
        if not group:
            continue
        if group in allowed_set:
            if group not in selected:
                selected.append(group)
        else:
            ignored.append(_safe_text(group, limit=80))
    if not selected:
        selected = list(allowed_groups)
    selected_apis: list[str] = []
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        if requirement["signal_group"] not in selected:
            continue
        for api in requirement["apis"]:
            api_name = str(api)
            if api_name not in selected_apis:
                selected_apis.append(api_name)
    return selected, ignored, selected_apis


def _provider_parity_candidate_symbols(
    packet: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    *,
    limit: int = PROVIDER_PARITY_DEFAULT_CANDIDATE_LIMIT,
) -> tuple[list[str], int, str]:
    source = "payload_or_packet_missing"
    raw_items: list[Any] = []
    for key in ["candidate_symbols", "symbols", "ts_codes", "candidates", "targets"]:
        value = payload_safe.get(key)
        if value in (None, "", [], {}):
            continue
        source = f"payload.{key}"
        if isinstance(value, str):
            raw_items = _split_candidate_text(value)
        elif isinstance(value, list):
            raw_items = list(value)
        else:
            raw_items = [value]
        break
    if not raw_items:
        candidate_rows = [row for row in _as_list(packet.get("candidate_rows")) if isinstance(row, dict)]
        raw_items = candidate_rows
        source = "packet.candidate_rows"
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in raw_items[:limit]:
        item = raw if isinstance(raw, Mapping) else {"symbol": raw}
        symbol = _candidate_code_from_item(item)
        info = _normalize_projection_symbol({"symbol": symbol})
        if info.get("symbol_valid") is True:
            symbol = str(info.get("normalized_symbol") or symbol)
        symbol = _safe_text(symbol, limit=32).upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols, max(0, len(raw_items) - limit), source


def _provider_parity_scope_ticket(
    *,
    selected_signal_groups: list[str],
    ignored_signal_groups: list[str],
    selected_apis: list[str],
    candidate_symbols: list[str],
    include_tushare: bool,
    include_deepseek: bool,
    user_approved: bool,
    credential_status: str,
) -> dict[str, Any]:
    scope_input = {
        "route": CANDIDATE_PROVIDER_PARITY_DRY_RUN_ROUTE,
        "task_type": CANDIDATE_PROVIDER_PARITY_DRY_RUN_TASK_TYPE,
        "selected_signal_groups": selected_signal_groups,
        "ignored_signal_groups": ignored_signal_groups,
        "selected_apis": selected_apis,
        "candidate_symbols": candidate_symbols,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "user_approved": user_approved,
        "credential_presence_status": credential_status,
    }
    serialized = json.dumps(scope_input, ensure_ascii=False, sort_keys=True, default=str)
    scope_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "schema_version": CANDIDATE_PROVIDER_PARITY_DRY_RUN_SCHEMA_VERSION,
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:16],
        "scope_hash_algorithm": "sha256",
        "scope_hash_input": scope_input,
        "credential_values_included": False,
        "env_key_names_included": False,
        "contains_secret": False,
    }


def _provider_parity_dry_run_row(
    criterion: str,
    status: str,
    evidence: str,
    next_action: str,
    *,
    passed: bool,
    blocks_real_execution: bool,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PROVIDER_PARITY_DRY_RUN_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_real_execution": bool(blocks_real_execution),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _build_candidate_provider_parity_dry_run(
    *,
    packet: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    include_tushare = _coerce_bool(payload_safe.get("include_tushare"), True)
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), True)
    user_approved = _coerce_bool(payload_safe.get("user_approved") or payload_safe.get("approved"), False)
    selected_groups, ignored_groups, selected_apis = _candidate_provider_parity_selected_groups(payload_safe)
    candidate_symbols, truncated_candidate_count, candidate_source = _provider_parity_candidate_symbols(packet, payload_safe)
    credential_rows, credential_summary = _quant_acceptance_credential_presence_rows(
        include_tushare=include_tushare,
        include_deepseek=include_deepseek,
    )
    missing_credentials = int(credential_summary.get("missing_provider_count") or 0)
    provider_rows = [row for row in _as_list(packet.get("provider_coverage_rows")) if isinstance(row, dict)]
    selected_provider_rows = [row for row in provider_rows if str(row.get("signal_group") or "") in set(selected_groups)]
    provider_gap_rows = [row for row in selected_provider_rows if row.get("coverage_status") != "available"]
    legacy_receipt = _as_dict(packet.get("legacy_parity_acceptance_receipt"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    browser_ready = browser_review.get("local_browser_qa_review_ready") is True
    browser_perf_ready = browser_review.get("candidate_browser_performance_evidence_passed") is True
    scope_ticket = _provider_parity_scope_ticket(
        selected_signal_groups=selected_groups,
        ignored_signal_groups=ignored_groups,
        selected_apis=selected_apis,
        candidate_symbols=candidate_symbols,
        include_tushare=include_tushare,
        include_deepseek=include_deepseek,
        user_approved=user_approved,
        credential_status=str(credential_summary.get("status") or "unknown"),
    )
    rows = [
        _provider_parity_dry_run_row(
            "explicit_user_approval_recorded",
            "passed_user_approved_dry_run" if user_approved else "blocked_user_approval_required",
            f"user_approved={user_approved}",
            "Require explicit user approval before any radar provider parity task can run.",
            passed=user_approved,
            blocks_real_execution=not user_approved,
        ),
        _provider_parity_dry_run_row(
            "candidate_scope_bound",
            "passed_bounded_candidate_scope" if candidate_symbols else "blocked_empty_candidate_scope",
            f"candidate_count={len(candidate_symbols)}; source={candidate_source}; truncated={truncated_candidate_count}",
            "Bind provider parity acceptance to current candidates/watchlist/search subset before broader worker scans.",
            passed=bool(candidate_symbols),
            blocks_real_execution=not candidate_symbols,
        ),
        _provider_parity_dry_run_row(
            "legacy_signal_parity_inventory_visible",
            "passed" if legacy_receipt.get("local_acceptance_receipt_ready") is True else "blocked_missing_legacy_parity_receipt",
            f"legacy_status={legacy_receipt.get('status') or 'missing'}; blockers={legacy_receipt.get('production_blocker_count', 0)}",
            "Keep old radar Top/Watch/Excluded, evidence links, score dimensions, trigger/invalidation, holding comparison, filters, fallback, and manual deep research parity visible.",
            passed=legacy_receipt.get("local_acceptance_receipt_ready") is True,
            blocks_real_execution=legacy_receipt.get("local_acceptance_receipt_ready") is not True,
        ),
        _provider_parity_dry_run_row(
            "provider_signal_groups_selected",
            "passed_selected_signal_groups",
            f"selected_signal_groups={selected_groups}; ignored_signal_groups={ignored_groups}",
            "Use only explicit signal groups and report ignored groups instead of silently widening scope.",
            passed=True,
            blocks_real_execution=False,
        ),
        _provider_parity_dry_run_row(
            "provider_api_scope_white_listed",
            "passed_provider_api_scope_bound",
            f"selected_apis={selected_apis}",
            "Record future Tushare APIs in a safe call ledger before claiming provider-backed radar parity.",
            passed=True,
            blocks_real_execution=False,
        ),
        _provider_parity_dry_run_row(
            "provider_coverage_gaps_visible",
            "pending_provider_gaps" if provider_gap_rows else "passed_no_local_provider_gap_reported",
            f"selected_provider_rows={len(selected_provider_rows)}; provider_gap_count={len(provider_gap_rows)}",
            "Run a separate real provider task only after gaps, permissions, empty windows, stale data, and row counts are ledgered.",
            passed=not provider_gap_rows,
            blocks_real_execution=bool(provider_gap_rows),
        ),
        _provider_parity_dry_run_row(
            "server_credential_presence_checked",
            "passed_no_values_read" if not missing_credentials else "blocked_missing_server_credentials",
            f"credential_presence_status={credential_summary.get('status')}; missing={missing_credentials}",
            "Configure missing server-side credentials, then rerun dry-run; never expose credential values or env key names.",
            passed=not missing_credentials,
            blocks_real_execution=bool(missing_credentials),
        ),
        _provider_parity_dry_run_row(
            "full_pool_worker_execution_required",
            "pending_worker_execution",
            "Dry-run did not execute full-pool worker scanning.",
            "Keep full-pool execution as a separate worker-backed task with progress, locks, and safe failure rows.",
            passed=False,
            blocks_real_execution=True,
        ),
        _provider_parity_dry_run_row(
            "deep_scan_worker_execution_required",
            "pending_deep_scan_execution",
            "Dry-run did not execute deep scan and did not call DeepSeek.",
            "Keep deep scan behind an explicit task with model ledger and sanitizer evidence if DeepSeek is used.",
            passed=False,
            blocks_real_execution=True,
        ),
        _provider_parity_dry_run_row(
            "browser_performance_evidence_required",
            "passed_local_browser_review" if browser_ready and browser_perf_ready else "pending_browser_performance_evidence",
            f"browser_review_ready={browser_ready}; browser_performance_ready={browser_perf_ready}",
            "Promote ignored local browser reports only after visual and performance evidence is reviewed.",
            passed=bool(browser_ready and browser_perf_ready),
            blocks_real_execution=not bool(browser_ready and browser_perf_ready),
        ),
        _provider_parity_dry_run_row(
            "deepseek_model_ledger_required",
            "pending_optional_model_ledger" if include_deepseek else "skipped_not_requested",
            "Dry-run did not call DeepSeek; optional model execution needs model ledger and sanitizer evidence.",
            "Record model_used, token usage, parse status, input/output hash, sanitizer result, and parse_failed discard.",
            passed=not include_deepseek,
            blocks_real_execution=include_deepseek,
        ),
        _provider_parity_dry_run_row(
            "trade_action_isolation_preserved",
            "passed_research_only",
            "Provider parity dry-run cannot execute trades, mutate holdings, or modify strategy action.",
            "Keep candidate radar research-only; candidate score is not a buy/sell instruction.",
            passed=True,
            blocks_real_execution=False,
        ),
        _provider_parity_dry_run_row(
            "production_promotion_review_required",
            "pending_promotion_review",
            "Provider/model/worker/browser evidence still needs redaction and production promotion review.",
            "Promote only after direct evidence exists and push gate remains green.",
            passed=False,
            blocks_real_execution=True,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("blocks_real_execution")]
    if not user_approved:
        status = "candidate_provider_parity_dry_run_blocked_user_approval_required"
        allowed_next_step = "rerun_dry_run_with_explicit_user_approval"
    elif not candidate_symbols:
        status = "candidate_provider_parity_dry_run_blocked_empty_candidate_scope"
        allowed_next_step = "provide_candidate_symbols_or_run_local_candidate_scan_first"
    elif missing_credentials:
        status = "candidate_provider_parity_dry_run_blocked_missing_credentials"
        allowed_next_step = "configure_server_credentials_then_rerun_dry_run"
    else:
        status = "candidate_provider_parity_dry_run_ready_real_execution_still_blocked"
        allowed_next_step = "implement_explicit_provider_backed_candidate_radar_parity_task_bound_to_scope_ticket"
    receipt = {
        "schema_version": CANDIDATE_PROVIDER_PARITY_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "local_candidate_radar_provider_parity_dry_run_no_provider_or_model_call",
        "task_type": CANDIDATE_PROVIDER_PARITY_DRY_RUN_TASK_TYPE,
        "route": CANDIDATE_PROVIDER_PARITY_DRY_RUN_ROUTE,
        "user_approved": user_approved,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "selected_signal_groups": selected_groups,
        "ignored_signal_groups": ignored_groups,
        "selected_apis": selected_apis,
        "candidate_symbols": candidate_symbols,
        "candidate_symbol_count": len(candidate_symbols),
        "candidate_symbol_truncated_count": truncated_candidate_count,
        "candidate_scope_source": candidate_source,
        "provider_coverage_gap_count": len(provider_gap_rows),
        "credential_presence_summary": credential_summary,
        "credential_presence_rows": credential_rows,
        "acceptance_scope_ticket": scope_ticket,
        "acceptance_scope_hash": scope_ticket["scope_hash"],
        "acceptance_scope_hash_short": scope_ticket["scope_hash_short"],
        "local_dry_run_ready": bool(user_approved and candidate_symbols),
        "ready_for_user_approved_provider_parity": bool(user_approved and candidate_symbols and not missing_credentials),
        "ready_to_execute_real_provider_parity_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_full_pool_execution_done": False,
        "worker_deep_scan_execution_done": False,
        "browser_performance_evidence_complete": bool(browser_ready and browser_perf_ready),
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "allowed_next_step": allowed_next_step,
        "missing_evidence_items": [
            "explicit real provider-backed candidate radar parity task implementation",
            "real Tushare provider call ledger for selected signal groups",
            "optional DeepSeek model ledger and sanitizer evidence",
            "worker-backed full-pool execution evidence",
            "worker-backed deep-scan execution evidence",
            "browser visual/performance promotion evidence",
            "redaction and production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat provider parity dry-run as real provider/model execution",
            "call Tushare or DeepSeek from React render",
            "start full-pool or deep-scan on page load",
            "retire legacy radar fallback from dry-run evidence",
            "promote dry-run to production radar replacement",
            "turn candidate score into buy/sell instruction",
            "mutate strategy action, price, holdings, or operation zones",
        ],
        "row_count": len(rows),
        "blocking_phase_count": len(blocking_rows),
        "credential_missing_provider_count": missing_credentials,
        "credential_present_provider_count": credential_summary.get("present_provider_count", 0),
        "credential_required_provider_count": credential_summary.get("required_provider_count", 0),
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
    }
    return receipt, rows, credential_rows


def _provider_parity_execution_request_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "provider_task_created": False,
        "provider_task_executed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": False,
        "deepseek_model_ledger_evidence_done": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _provider_parity_acceptance_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "provider_task_created": False,
        "provider_task_executed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": False,
        "deepseek_model_ledger_evidence_done": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_provider_parity_acceptance_apis(
    selected_apis: list[Any],
    *,
    max_apis: int,
) -> tuple[list[str], list[str]]:
    supported = set(getattr(tushare_task_service, "ALL_REFRESH_APIS", ()))
    normalized: list[str] = []
    skipped: list[str] = []
    for raw_api in selected_apis:
        api = PROVIDER_PARITY_ACCEPTANCE_API_ALIASES.get(str(raw_api), str(raw_api))
        if api not in supported:
            skipped.append(str(raw_api))
            continue
        if api not in normalized:
            normalized.append(api)
    preferred = ["trade_cal"] + [api for api in PROVIDER_PARITY_ACCEPTANCE_LIGHT_APIS if api in normalized]
    for api in normalized:
        if api not in preferred:
            preferred.append(api)
    limit = max(1, int(max_apis or len(preferred)))
    executed = preferred[:limit]
    if "trade_cal" not in executed:
        executed = ["trade_cal"] + executed[: max(0, limit - 1)]
    skipped.extend([api for api in normalized if api not in executed])
    return executed, skipped


def _candidate_provider_parity_acceptance_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any],
    provider_tasks: list[Mapping[str, Any]],
    executed_apis: list[str],
    skipped_apis: list[str],
    explicit_request: bool,
    task_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    execution_request = _as_dict(packet.get("provider_parity_execution_request_receipt"))
    operator_approved = _coerce_bool(
        payload_safe.get("operator_approved") or payload_safe.get("user_approved") or payload_safe.get("approved"),
        False,
    )
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), False)
    requested_scope_hash = _safe_text(
        payload_safe.get("acceptance_scope_hash") or payload_safe.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(execution_request.get("acceptance_scope_hash") or "", limit=128)
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    execution_request_ready = execution_request.get("local_execution_request_ready") is True
    candidate_symbols = [str(symbol) for symbol in _as_list(execution_request.get("candidate_symbols"))]
    provider_ledger = [
        row
        for provider_task in provider_tasks
        for row in _as_list(provider_task.get("call_ledger"))
        if isinstance(row, dict)
    ]
    success_rows = [row for row in provider_ledger if row.get("call_status") == "success"]
    empty_rows = [row for row in provider_ledger if row.get("call_status") == "empty"]
    failed_rows = [
        row
        for row in provider_ledger
        if row.get("call_status") == "failed" or str(row.get("call_status") or "").startswith("blocked_")
    ]
    terminal_ok_rows = success_rows + empty_rows
    provider_executed = bool(provider_tasks)
    api_call_count = len(provider_ledger)
    provider_evidence_done = bool(
        provider_executed
        and provider_ledger
        and len(terminal_ok_rows) == api_call_count
        and not failed_rows
        and all(row.get("tushare_called") is True for row in provider_ledger)
    )
    has_trade_cal_sample = any(row.get("api") == "trade_cal" for row in success_rows)
    candidate_count = len(candidate_symbols[: max(1, len(provider_tasks))])
    has_core_light_samples = bool(
        candidate_count > 0
        and any(row.get("api") in {"moneyflow", "daily", "daily_basic"} for row in terminal_ok_rows)
    )
    rows = [
        _provider_parity_acceptance_row(
            "explicit_post_provider_parity_acceptance_done",
            "passed_explicit_post" if explicit_request else "blocked_missing_explicit_post",
            passed=explicit_request,
            production_blocker=not explicit_request,
            evidence=f"task_id={task_id}",
            next_action="Use only POST /api/candidate-radar/provider-parity-acceptance.",
        ),
        _provider_parity_acceptance_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            production_blocker=not operator_approved,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before provider execution.",
        ),
        _provider_parity_acceptance_row(
            "execution_request_ready",
            "passed_execution_request_ready" if execution_request_ready else "blocked_execution_request_missing",
            passed=execution_request_ready,
            production_blocker=not execution_request_ready,
            evidence=f"provider_request={execution_request.get('status') or 'missing'}",
            next_action="Create a scope-bound provider parity execution request before provider acceptance.",
        ),
        _provider_parity_acceptance_row(
            "acceptance_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            production_blocker=not scope_hash_matches,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind provider execution to the latest provider parity execution-request scope hash.",
        ),
        _provider_parity_acceptance_row(
            "deepseek_model_ledger_policy",
            "passed_deepseek_skipped_by_request" if not include_deepseek else "blocked_deepseek_not_enabled_this_cycle",
            passed=not include_deepseek,
            production_blocker=include_deepseek,
            evidence=f"include_deepseek={include_deepseek}; model_execution_implemented=false",
            next_action="Run DeepSeek benchmark/model ledger in a separate explicitly approved cycle.",
        ),
        _provider_parity_acceptance_row(
            "tushare_provider_parity_call_ledger",
            "passed_tushare_provider_parity_ledger" if provider_evidence_done else "blocked_tushare_provider_ledger_missing_or_failed",
            passed=provider_evidence_done,
            production_blocker=not provider_evidence_done,
            evidence=(
                f"api_terminal_ok={len(terminal_ok_rows)}/{api_call_count}; "
                f"api_success={len(success_rows)}; api_empty={len(empty_rows)}; "
                f"executed_apis={executed_apis}; skipped_apis={skipped_apis}"
            ),
            next_action="Collect safe Tushare provider call ledger for the bounded radar candidate/API scope.",
        ),
        _provider_parity_acceptance_row(
            "worker_browser_promotion_still_pending",
            "passed_provider_light_evidence_only",
            passed=True,
            production_blocker=True,
            evidence="Provider ledger is captured, but worker runtime, browser QA, legacy retirement, and promotion are separate evidence.",
            next_action="Continue with worker/browser/promotion evidence after reviewing provider parity ledger.",
        ),
        _provider_parity_acceptance_row(
            "no_trade_action_secret_boundary",
            "passed_no_trade_action_secret_boundary",
            passed=True,
            production_blocker=False,
            evidence="No trade execution, no strategy action mutation, no credential value exposure.",
            next_action="Keep Radar candidates research-only.",
        ),
    ]
    blocking_rows = [row for row in rows if row.get("production_blocker")]
    if include_deepseek:
        status = "candidate_provider_parity_acceptance_blocked_deepseek_not_enabled_this_cycle"
    elif not execution_request_ready:
        status = "candidate_provider_parity_acceptance_blocked_execution_request_required"
    elif not scope_hash_matches:
        status = "candidate_provider_parity_acceptance_blocked_scope_hash_mismatch"
    elif not provider_evidence_done:
        status = "candidate_provider_parity_acceptance_blocked_provider_ledger_missing_or_failed"
    else:
        status = "candidate_provider_parity_acceptance_ready_tushare_light_deepseek_skipped"
    artifact = {
        "schema_version": "candidate_radar_provider_parity_tushare_light_evidence.v1",
        "status": (
            "candidate_radar_provider_parity_tushare_light_evidence_ready"
            if provider_evidence_done
            else "candidate_radar_provider_parity_tushare_light_evidence_blocked"
        ),
        "direct_evidence_layer": "L3_real_tushare_provider_call_ledger_supporting_candidate_radar_provider_parity",
        "task_id": task_id,
        "candidate_count": candidate_count,
        "candidate_symbols": candidate_symbols[:candidate_count],
        "selected_apis": executed_apis,
        "skipped_apis": skipped_apis,
        "api_call_count": api_call_count,
        "api_success_count": len(success_rows),
        "api_empty_count": len(empty_rows),
        "api_terminal_ok_count": len(terminal_ok_rows),
        "api_failed_count": len(failed_rows),
        "all_selected_api_calls_succeeded": len(success_rows) == api_call_count,
        "all_selected_api_calls_terminal_ok": provider_evidence_done,
        "has_core_light_samples_for_all_candidates": has_core_light_samples,
        "has_trade_cal_sample": has_trade_cal_sample,
        "provider_call_ledger": provider_ledger,
        "external_calls_triggered": provider_executed,
        "tushare_called": provider_executed,
        "deepseek_called": False,
        "github_called": False,
        "deepseek_model_execution_done": False,
        "provider_backed_acceptance_done": False,
        "production_radar_replacement_complete": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }
    receipt = {
        "schema_version": CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_candidate_radar_provider_parity_acceptance_tushare_light_deepseek_skipped",
        "mode": "button_gated_provider_parity_acceptance",
        "ltg": "LTG-13/LTG-02",
        "route": CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_ROUTE,
        "task_type": CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_TASK_TYPE,
        "task_id": task_id,
        "candidate_symbols": candidate_symbols,
        "candidate_symbol_count": len(candidate_symbols),
        "selected_apis": executed_apis,
        "skipped_apis": skipped_apis,
        "acceptance_scope_hash": expected_scope_hash,
        "acceptance_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_acceptance_scope_hash_matches_latest": scope_hash_matches,
        "operator_approved": operator_approved,
        "execution_request_ready": execution_request_ready,
        "provider_execution_implemented": provider_executed,
        "model_execution_implemented": False,
        "provider_task_created": provider_executed,
        "provider_task_executed": provider_executed,
        "tushare_call_ledger_evidence_done": provider_evidence_done,
        "deepseek_model_ledger_evidence_done": False,
        "deepseek_skipped_by_request": not include_deepseek,
        "direct_evidence_verified": provider_evidence_done and not include_deepseek,
        "provider_call_ledger": provider_ledger,
        "provider_api_call_count": api_call_count,
        "provider_api_success_count": len(success_rows),
        "provider_api_empty_count": len(empty_rows),
        "provider_api_terminal_ok_count": len(terminal_ok_rows),
        "provider_api_failed_count": len(failed_rows),
        "provider_parity_tushare_light_evidence_path": str(CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH),
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "provider_backed_acceptance_done": False,
        "production_blocker_count": len(blocking_rows),
        "production_blockers": [row["criterion"] for row in blocking_rows],
        "external_calls_triggered_by_task": provider_executed,
        "tushare_called_by_task": provider_executed,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "rows": rows,
    }
    return receipt, rows, artifact


def _candidate_radar_provider_parity_execution_request(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_request: bool = False,
    task_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = payload_safe or {}
    operator_approved = _coerce_bool(
        payload.get("operator_approved") or payload.get("user_approved") or payload.get("approved"),
        False,
    )
    dry_run = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    requested_scope_hash = _safe_text(
        payload.get("acceptance_scope_hash") or payload.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(dry_run.get("acceptance_scope_hash") or "", limit=128)
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    dry_run_scope_visible = bool(expected_scope_hash)
    credential_missing = int(dry_run.get("credential_missing_provider_count") or 0)
    dry_run_ready = bool(
        dry_run_scope_visible
        and dry_run.get("status") == "candidate_provider_parity_dry_run_ready_real_execution_still_blocked"
        and dry_run.get("user_approved") is True
        and dry_run.get("ready_for_user_approved_provider_parity") is True
        and credential_missing == 0
    )
    candidate_symbols = [str(symbol) for symbol in _as_list(dry_run.get("candidate_symbols"))]
    selected_signal_groups = [str(group) for group in _as_list(dry_run.get("selected_signal_groups"))]
    selected_apis = [str(api) for api in _as_list(dry_run.get("selected_apis"))]
    include_tushare = dry_run.get("include_tushare") is True
    include_deepseek = dry_run.get("include_deepseek") is True
    rows = [
        _provider_parity_execution_request_row(
            "explicit_post_provider_parity_execution_request_done",
            "passed_explicit_post" if explicit_request else "blocked_missing_explicit_post",
            passed=explicit_request,
            local_blocker=not explicit_request,
            production_blocker=False,
            evidence=f"explicit_request={explicit_request}; task_id={task_id or ''}",
            next_action="Use only POST /api/candidate-radar/provider-parity-execution-request to create this request ticket.",
        ),
        _provider_parity_execution_request_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_request and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before any future provider/model radar task.",
        ),
        _provider_parity_execution_request_row(
            "provider_parity_dry_run_scope_ticket_visible",
            "passed_scope_ticket_visible" if dry_run_scope_visible else "blocked_provider_parity_dry_run_missing",
            passed=dry_run_scope_visible,
            local_blocker=not dry_run_scope_visible,
            production_blocker=False,
            evidence=f"dry_run_status={dry_run.get('status') or 'missing'}; scope={dry_run.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Run the user-approved provider parity dry-run before requesting real provider execution.",
        ),
        _provider_parity_execution_request_row(
            "acceptance_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            local_blocker=explicit_request and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind this request to the latest provider parity dry-run scope hash.",
        ),
        _provider_parity_execution_request_row(
            "provider_parity_dry_run_ready",
            "passed_dry_run_ready" if dry_run_ready else "blocked_dry_run_not_ready",
            passed=dry_run_ready,
            local_blocker=explicit_request and not dry_run_ready,
            production_blocker=False,
            evidence=(
                f"ready_for_user_approved_provider_parity={dry_run.get('ready_for_user_approved_provider_parity')}; "
                f"credential_missing_for_future_execution={credential_missing}"
            ),
            next_action="Resolve provider parity dry-run blockers before creating a future provider task.",
        ),
        _provider_parity_execution_request_row(
            "candidate_provider_scope_bound",
            "passed_candidate_provider_scope_bound" if candidate_symbols and selected_apis else "blocked_candidate_or_api_scope_missing",
            passed=bool(candidate_symbols and selected_apis),
            local_blocker=explicit_request and not bool(candidate_symbols and selected_apis),
            production_blocker=False,
            evidence=f"candidate_count={len(candidate_symbols)}; selected_apis={selected_apis}; signal_groups={selected_signal_groups}",
            next_action="Keep future provider parity execution limited to the dry-run candidate/API/signal scope.",
        ),
        _provider_parity_execution_request_row(
            "target_provider_task_route_declared",
            "passed_target_route_declared",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="future POST /api/candidate-radar/provider-parity-acceptance",
            next_action="Implement the future real provider parity task only after explicit user approval.",
        ),
        _provider_parity_execution_request_row(
            "provider_call_ledger_still_pending",
            "passed_request_only",
            passed=True,
            local_blocker=False,
            production_blocker=True,
            evidence="Request ticket does not create or execute a Tushare/provider task.",
            next_action="Run a separate approved provider task with safe call ledger evidence before promotion.",
        ),
        _provider_parity_execution_request_row(
            "model_browser_promotion_still_pending",
            "passed_request_only",
            passed=True,
            local_blocker=False,
            production_blocker=True,
            evidence="DeepSeek model ledger, browser promotion, legacy retirement, and production replacement remain separate evidence.",
            next_action="Keep model/browser/promotion evidence separate from this provider request ticket.",
        ),
        _provider_parity_execution_request_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="No Tushare/DeepSeek/GitHub call, no provider task creation, no trade/action mutation, no secret exposure.",
            next_action="Preserve this boundary while adding future provider/model evidence.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    if not explicit_request:
        status = "candidate_provider_parity_execution_request_missing"
        allowed_next_step = "create_button_gated_provider_parity_execution_request"
    elif not operator_approved:
        status = "candidate_provider_parity_execution_request_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not dry_run_scope_visible:
        status = "candidate_provider_parity_execution_request_blocked_dry_run_required"
        allowed_next_step = "run_provider_parity_dry_run"
    elif not requested_scope_hash:
        status = "candidate_provider_parity_execution_request_blocked_scope_hash_required"
        allowed_next_step = "bind_latest_provider_parity_scope_hash"
    elif not scope_hash_matches:
        status = "candidate_provider_parity_execution_request_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_provider_parity_scope_hash"
    elif not dry_run_ready:
        status = "candidate_provider_parity_execution_request_blocked_dry_run_not_ready"
        allowed_next_step = "resolve_provider_parity_dry_run_blockers"
    else:
        status = "candidate_provider_parity_execution_request_ready_manual_provider_task_pending"
        allowed_next_step = "manual_future_provider_parity_task_implementation_with_call_and_model_ledgers"
    local_ready = explicit_request and operator_approved and not local_blockers
    receipt = {
        "schema_version": CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_candidate_radar_provider_parity_execution_request_no_provider_or_model_call",
        "mode": "button_gated_local_provider_parity_execution_request",
        "ltg": "LTG-13/LTG-02/LTG-07",
        "route": CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_ROUTE,
        "task_type": CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_TASK_TYPE,
        "request_task_id": task_id or "",
        "explicit_provider_parity_execution_request_done": explicit_request,
        "operator_approved": operator_approved,
        "local_execution_request_ready": local_ready,
        "ready_for_manual_provider_parity_task_submission": local_ready,
        "provider_parity_dry_run_scope_ticket_visible": dry_run_scope_visible,
        "provider_parity_dry_run_ready": dry_run_ready,
        "acceptance_scope_hash": expected_scope_hash,
        "acceptance_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_acceptance_scope_hash": requested_scope_hash,
        "requested_acceptance_scope_hash_matches_latest": scope_hash_matches,
        "provider_parity_scope_hash": expected_scope_hash,
        "provider_parity_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_provider_parity_scope_hash": requested_scope_hash,
        "requested_provider_parity_scope_hash_matches_latest": scope_hash_matches,
        "candidate_symbols": candidate_symbols,
        "candidate_symbol_count": len(candidate_symbols),
        "selected_signal_groups": selected_signal_groups,
        "selected_apis": selected_apis,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "credential_missing_provider_count": credential_missing,
        "target_provider_task_route": "future POST /api/candidate-radar/provider-parity-acceptance",
        "target_provider_task_type": "future_run_candidate_radar_provider_parity_acceptance",
        "allowed_next_step": allowed_next_step,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "blocking_criteria": local_blockers,
        "production_blockers": production_blockers,
        "provider_task_created": False,
        "provider_task_executed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": False,
        "deepseek_model_ledger_evidence_done": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "production_radar_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "not_allowed_next_steps": [
            "create provider task from execution request",
            "call Tushare/DeepSeek/GitHub from execution request",
            "treat execution request as provider-backed parity",
            "treat request as browser promotion or legacy retirement",
            "promote request to production radar replacement",
            "turn candidate rows into buy/sell instructions",
            "mutate strategy action, price, holdings, or operation zones",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "row_count": len(rows),
        "rows": rows,
        "note": "This local request ticket binds provider parity dry-run scope for a future provider task. It does not call Tushare, call DeepSeek, execute trades, or complete radar production replacement.",
    }
    return receipt, rows


def _snapshot_with_quant_projection(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    symbol_info = _normalize_projection_symbol(payload_safe)
    overlay = dict(snapshot_map)
    existing_radar = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    symbol = str(symbol_info.get("normalized_symbol") or "")
    candidate_rows: list[dict[str, Any]] = []
    if symbol_info.get("symbol_valid") is True:
        candidate_rows = [
            {
                "rank": 1,
                "ticker": symbol,
                "name": _safe_text(payload_safe.get("name") or payload_safe.get("stock_name") or "", limit=80),
                "score": None,
                "status_label": "本地量化推演待补证",
                "action_state": "research_only",
                "tone": "warn",
                "evidence_chain_summary": "搜票量化推演本地回执；真实 Tushare / Factor / Next Session / DeepSeek 证据仍待显式任务补齐。",
                "trigger_condition": "等待 provider-backed freshness 和因子证据",
                "invalidation_condition": "stale / expired / historical / missing evidence 不进入当前 evidence",
                "source": "search_quant_projection_local_receipt",
                "updated_at": _now_iso(),
                "data_gaps": [
                    "tushare_light_refresh_pending",
                    "factor_next_session_refresh_pending",
                    "deepseek_pro_explanation_pending",
                    "echarts_payload_refresh_pending",
                ],
            }
        ]
    receipt, rows = _build_quant_projection_receipt(
        symbol_info=symbol_info,
        payload_safe=payload_safe,
        candidate_count=len(candidate_rows),
    )
    overlay["next_ticket_candidates"] = candidate_rows
    overlay["radar_packet"] = {
        **existing_radar,
        "status": "ready" if candidate_rows else "blocked",
        "source": "搜票量化推演本地任务",
        "summary": "已生成搜票量化推演本地回执；未调用外部源，真实证据仍需后续显式任务。",
        "generated_at": _now_iso(),
        "total_count": len(candidate_rows),
        "top_candidates": candidate_rows,
        "watch_candidates": [],
        "excluded_candidates": _as_list(existing_radar.get("excluded_candidates")),
        "manual_required_text": "量化推演是 research-only，本地回执不能作为买卖指令。",
    }
    overlay["search_quant_projection_receipt"] = receipt
    overlay["search_quant_projection_rows"] = rows
    return overlay, receipt, rows


def _snapshot_fingerprint(snapshot_map: Mapping[str, Any]) -> str:
    serialized = json.dumps(snapshot_map, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _first_present_key(snapshot_map: Mapping[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = snapshot_map.get(key)
        if value not in (None, {}, []):
            return key
    return ""


def _source_group_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for spec in LEGACY_RADAR_SIGNAL_GROUPS:
        source_keys = [str(item) for item in spec["source_keys"]]
        present_key = _first_present_key(snapshot_map, source_keys)
        rows.append(
            {
                "group": spec["group"],
                "source_keys": source_keys,
                "present": bool(present_key),
                "source_key_used": present_key,
                "role": spec["role"],
                "migration_status": "mapped" if present_key else "missing_reported",
                "does_not_silently_drop": True,
            }
        )
    return rows


def _candidate_rows(candidates: Any, *, max_rows: int = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(candidates)[:max_rows], start=1):
        item = _as_dict(raw)
        if not item:
            continue
        rows.append(
            {
                "rank": item.get("rank") or idx,
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "score": item.get("score"),
                "status_label": item.get("status_label"),
                "action_state": item.get("action_state"),
                "tone": item.get("tone"),
                "evidence_chain_summary": item.get("evidence_chain_summary"),
                "trigger_condition": item.get("trigger_condition"),
                "invalidation_condition": item.get("invalidation_condition"),
                "source": item.get("source"),
                "updated_at": item.get("updated_at"),
                "data_gaps": item.get("data_gaps"),
            }
        )
    return rows


def _raw_candidate_input_count(snapshot: Mapping[str, Any]) -> int:
    raw_radar = _as_dict(snapshot.get("radar_packet") or snapshot.get("command_center_radar_packet"))
    raw_candidates = _as_list(snapshot.get("next_ticket_candidates")) or _as_list(raw_radar.get("top_candidates"))
    return len(raw_candidates)


def _candidate_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for item in rows if str(item.get("action_state") or "").strip() in {"可准备", "作战准备"})
    observe = sum(1 for item in rows if "观察" in str(item.get("action_state") or item.get("status_label") or ""))
    verify = sum(1 for item in rows if "验证" in str(item.get("action_state") or item.get("status_label") or item.get("tone") or ""))
    return {
        "candidate_count": len(rows),
        "ready_count": ready,
        "observe_count": observe,
        "verify_count": verify,
    }


def _candidate_data_gap_count(row: Mapping[str, Any]) -> int:
    value = row.get("data_gaps")
    if isinstance(value, list):
        return len([item for item in value if item not in (None, "", [], {})])
    if value in (None, "", [], {}):
        return 0
    return 1


def _candidate_priority_bucket(row: Mapping[str, Any], gap_count: int) -> str:
    action_text = str(row.get("action_state") or row.get("status_label") or row.get("tone") or "")
    if gap_count:
        return "gap_first_review"
    if "验证" in action_text:
        return "verification_required"
    if "观察" in action_text:
        return "observe_only"
    if str(row.get("score") or "").strip():
        return "ranked_cache_candidate"
    return "manual_review_required"


def _candidate_explanation_missing_fields(row: Mapping[str, Any]) -> list[str]:
    required_fields = [
        "rank",
        "ticker",
        "score",
        "evidence_chain_summary",
        "trigger_condition",
        "invalidation_condition",
        "data_gaps",
        "action_state",
    ]
    return [field for field in required_fields if row.get(field) in (None, "", [], {})]


def _candidate_priority_explanation_contract(
    candidate_rows: list[dict[str, Any]],
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    freshness_state = _as_dict(coverage.get("freshness_state"))
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(candidate_rows[:PRIORITY_EXPLANATION_LIMIT], start=1):
        gap_count = _candidate_data_gap_count(row)
        missing_fields = _candidate_explanation_missing_fields(row)
        explanation_status = (
            "gap_visible"
            if gap_count
            else "partial_cache_explanation"
            if missing_fields
            else "complete_cache_explanation"
        )
        rows.append(
            {
                "display_rank": row.get("rank") or index,
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "cached_score": row.get("score"),
                "priority_bucket": _candidate_priority_bucket(row, gap_count),
                "explanation_status": explanation_status,
                "rank_source": "existing_candidate_rows_order",
                "score_source": "existing_cache_score_preserved" if row.get("score") not in (None, "") else "score_missing",
                "action_state": row.get("action_state"),
                "status_label": row.get("status_label"),
                "evidence_summary_present": row.get("evidence_chain_summary") not in (None, "", [], {}),
                "trigger_condition_present": row.get("trigger_condition") not in (None, "", [], {}),
                "invalidation_condition_present": row.get("invalidation_condition") not in (None, "", [], {}),
                "data_gap_count": gap_count,
                "missing_explanation_fields": missing_fields,
                "manual_review_required": True,
                "uses_existing_rank_only": True,
                "uses_existing_score_only": True,
                "does_not_recompute_score": True,
                "does_not_sort_candidates": True,
                "candidate_is_not_buy_instruction": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    explanation_gap_count = sum(1 for row in rows if row["explanation_status"] != "complete_cache_explanation")
    data_gap_visible_count = sum(1 for row in rows if int(row.get("data_gap_count") or 0) > 0)
    missing_score_count = sum(1 for row in rows if row["score_source"] == "score_missing")
    return {
        "schema_version": "candidate_radar_priority_explanation.v1",
        "status": "candidate_priority_explanation_ready" if rows else "candidate_priority_explanation_empty",
        "scope": "local_cache_rank_explanation_not_rescore_or_trade_signal",
        "scan_mode": scan_mode,
        "row_limit": PRIORITY_EXPLANATION_LIMIT,
        "candidate_row_count": len(candidate_rows),
        "explained_candidate_count": len(rows),
        "explanation_gap_count": explanation_gap_count,
        "data_gap_visible_count": data_gap_visible_count,
        "missing_score_count": missing_score_count,
        "freshness_state": freshness_state.get("state") or "unknown",
        "freshness_source": freshness_state.get("source") or "missing",
        "sort_order_source": "existing_candidate_rows_order",
        "cached_rank_preserved": True,
        "cached_score_preserved": True,
        "uses_existing_rank_only": True,
        "uses_existing_score_only": True,
        "does_not_recompute_score": True,
        "does_not_sort_candidates": True,
        "does_not_calculate_action": True,
        "manual_review_required": True,
        "priority_explanation_is_not_trade_signal": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "production_radar_replacement_complete": False,
        "row_count": len(rows),
        "rows": rows,
        "note": "This contract explains visible cached candidate rank/score and missing evidence fields. It does not rescore, reorder, refresh providers, call models, or create trading instructions.",
    }


def _has_any_candidate_field(candidate_rows: list[dict[str, Any]], fields: list[str]) -> bool:
    for row in candidate_rows:
        for field in fields:
            if row.get(field) not in (None, "", [], {}):
                return True
    return False


def _has_any_packet_field(packet: Mapping[str, Any], fields: list[str]) -> bool:
    for field in fields:
        value = packet.get(field)
        if value not in (None, "", [], {}):
            return True
    return False


def _legacy_parity_rows(
    *,
    snapshot_map: Mapping[str, Any],
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    evidence_recovery_actions: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_group_map = {row["group"]: row for row in _source_group_rows(snapshot_map)}
    for item in LEGACY_RADAR_PARITY_ITEMS:
        key = str(item["key"])
        support = str(item["current_support"])
        present = False
        status = support
        if key == "top_watch_excluded_split":
            present = bool(candidate_rows or excluded_candidates)
            status = "mapped" if present else "missing_reported"
        elif key == "evidence_links":
            present = bool(_has_any_candidate_field(candidate_rows, ["evidence_chain_summary"]) or evidence_recovery_actions)
            status = "mapped_or_gap_reported" if present else "missing_reported"
        elif key == "scoring_dimensions":
            present = bool(_has_any_candidate_field(candidate_rows, ["score"]))
            status = "partial_mapped" if present else "missing_reported"
        elif key == "trigger_invalidation":
            present = bool(_has_any_candidate_field(candidate_rows, ["trigger_condition", "invalidation_condition"]))
            status = "mapped" if present else "missing_reported"
        elif key == "holding_comparison":
            present = any(
                snapshot_map.get(source_key) not in (None, "", [], {})
                for source_key in ("position_risk_budget", "holding_action", "position_context", "current_holding_context")
            )
            status = "partial_mapped" if present else "missing_reported"
        elif key == "candidate_pool_sources":
            present = bool(radar_packet.get("source") or _has_any_candidate_field(candidate_rows, ["source"]))
            status = "quick_cache_only" if present else "missing_reported"
        elif key == "scan_filters":
            present = False
            status = "future_task_required"
        elif key == "timeout_and_fallback":
            present = bool(radar_packet or candidate_rows)
            status = "mapped_from_cache" if present else "missing_reported"
        elif key == "manual_deep_research":
            present = False
            status = "manual_only_future_task"

        source_group = source_group_map.get("radar_packet") if key in {"top_watch_excluded_split", "timeout_and_fallback"} else None
        rows.append(
            {
                "key": key,
                "label": item["label"],
                "legacy_sources": item["legacy_sources"],
                "current_fields": item["current_fields"],
                "present_in_current_cache": present,
                "migration_status": status,
                "target_state": item["target_state"],
                "source_key_used": source_group.get("source_key_used") if source_group else "",
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _legacy_output_contract_rows(
    *,
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in LEGACY_RADAR_OUTPUT_CONTRACT_FIELDS:
        field = str(item["field"])
        if field == "top_candidates":
            present = bool(candidate_rows)
            source = "candidate_rows/radar_packet.top_candidates"
        elif field == "excluded_candidates":
            present = bool(excluded_candidates)
            source = "radar_packet.excluded_candidates"
        elif field == "watch_candidates":
            present = bool(_as_list(radar_packet.get("watch_candidates")))
            source = "radar_packet.watch_candidates"
        elif field in {"trigger_condition", "invalidation_condition", "data_gaps"}:
            present = _has_any_candidate_field(candidate_rows, [field])
            source = "candidate_rows"
        elif field == "evidence_items":
            present = _has_any_candidate_field(candidate_rows, ["evidence_chain_summary"])
            source = "candidate_rows.evidence_chain_summary"
        else:
            present = _has_any_packet_field(radar_packet, [field])
            source = "radar_packet"
        rows.append(
            {
                "field": field,
                "role": item["role"],
                "required_for": item["required_for"],
                "present": bool(present),
                "source": source,
                "migration_status": "mapped" if present else "missing_reported",
                "does_not_invent_value": True,
            }
        )
    return rows


def _legacy_parity_inventory(
    *,
    snapshot_map: Mapping[str, Any],
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    evidence_recovery_actions: list[Any],
) -> dict[str, Any]:
    parity_rows = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    output_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    mapped = [row for row in parity_rows if str(row.get("migration_status")) in {"mapped", "mapped_or_gap_reported", "partial_mapped", "mapped_from_cache", "quick_cache_only"}]
    gaps = [row for row in parity_rows if "missing" in str(row.get("migration_status")) or "future" in str(row.get("migration_status"))]
    return {
        "status": "partial_parity",
        "scope": "legacy_next_ticket_radar_inventory",
        "legacy_module_files": ["next_stock_radar.py", "command_center_radar_packet.py", "app.py"],
        "parity_row_count": len(parity_rows),
        "mapped_or_partial_count": len(mapped),
        "gap_or_future_count": len(gaps),
        "output_contract_field_count": len(output_rows),
        "output_contract_mapped_count": sum(1 for row in output_rows if row["present"]),
        "quick_scan_is_full_replacement": False,
        "slow_paths_are_future_button_tasks": True,
        "deep_research_is_manual_only_future": True,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _legacy_parity_acceptance_row(
    item_key: str,
    category: str,
    label: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "item_key": item_key,
        "category": category,
        "label": label,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_ready": bool(production_ready),
        "blocks_production_replacement": not bool(production_ready),
        "gap_visible": not bool(production_ready),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _legacy_parity_acceptance_receipt(
    *,
    parity_inventory: Mapping[str, Any],
    parity_rows: list[dict[str, Any]],
    output_contract_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    production_ready_statuses = {"mapped", "mapped_from_cache"}
    rows: list[dict[str, Any]] = []
    for row in parity_rows:
        migration_status = str(row.get("migration_status") or "missing_reported")
        production_ready = migration_status in production_ready_statuses
        rows.append(
            _legacy_parity_acceptance_row(
                str(row.get("key") or ""),
                "legacy_parity_item",
                str(row.get("label") or row.get("key") or ""),
                "production_ready" if production_ready else "gap_visible",
                local_contract_passed=True,
                production_ready=production_ready,
                evidence=(
                    f"migration_status={migration_status}; present_in_current_cache="
                    f"{bool(row.get('present_in_current_cache'))}; target={row.get('target_state')}"
                ),
                next_action=(
                    "Keep mapped behavior covered in React/cache acceptance."
                    if production_ready
                    else "Map this legacy radar behavior with provider/worker/browser evidence or keep Streamlit fallback visible."
                ),
            )
        )
    for row in output_contract_rows:
        present = row.get("present") is True
        rows.append(
            _legacy_parity_acceptance_row(
                str(row.get("field") or ""),
                "legacy_output_field",
                str(row.get("field") or ""),
                "production_ready" if present else "missing_reported",
                local_contract_passed=True,
                production_ready=present,
                evidence=f"source={row.get('source')}; required_for={row.get('required_for')}; present={present}",
                next_action=(
                    "Preserve this output field in Candidate Radar replacement."
                    if present
                    else "Expose this missing output field as a gap; do not invent values before retiring legacy radar."
                ),
            )
        )
    local_blockers = [row["item_key"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["item_key"] for row in rows if row.get("blocks_production_replacement")]
    ready_count = sum(1 for row in rows if row.get("production_ready"))
    receipt = {
        "schema_version": "candidate_radar_legacy_parity_acceptance_receipt.v1",
        "status": "legacy_parity_acceptance_local_ready_production_pending" if not local_blockers else "legacy_parity_acceptance_blocked",
        "scope": "local_legacy_radar_parity_acceptance_not_production_replacement",
        "ltg": "LTG-13",
        "local_acceptance_receipt_ready": not local_blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "parity_inventory_status": parity_inventory.get("status"),
        "parity_item_count": int(parity_inventory.get("parity_row_count") or len(parity_rows)),
        "mapped_or_partial_count": int(parity_inventory.get("mapped_or_partial_count") or 0),
        "gap_or_future_count": int(parity_inventory.get("gap_or_future_count") or 0),
        "output_contract_field_count": int(parity_inventory.get("output_contract_field_count") or len(output_contract_rows)),
        "output_contract_mapped_count": int(parity_inventory.get("output_contract_mapped_count") or 0),
        "receipt_row_count": len(rows),
        "production_ready_count": ready_count,
        "production_blocker_count": len(production_blockers),
        "local_blocker_count": len(local_blockers),
        "production_blockers": production_blockers,
        "local_blockers": local_blockers,
        "required_before_legacy_retirement": [
            "top_watch_excluded_split",
            "evidence_links",
            "scoring_dimensions",
            "trigger_invalidation",
            "holding_comparison",
            "candidate_pool_sources",
            "scan_filters",
            "timeout_and_fallback",
            "manual_deep_research",
            "legacy_output_contract_fields",
        ],
        "not_allowed_next_steps": [
            "treat_gap_reported_as_feature_parity_complete",
            "retire_streamlit_radar_before_provider_worker_browser_acceptance",
            "claim_quick_scan_as_full_replacement",
            "invent_missing_legacy_output_fields",
            "convert_candidate_score_to_strategy_action",
        ],
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_candidate_radar_legacy_parity_acceptance_receipt",
                "source_snapshot": "legacy_parity_rows_and_output_contract_rows",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_parity_acceptance_receipt",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt turns legacy next-ticket radar parity into explicit acceptance rows. It is local evidence only; production replacement still requires provider-backed parity, worker full/deep scans, browser visual/performance QA, and legacy retirement review.",
    }
    return receipt, rows


def _candidate_call_ledger_row(
    *,
    api: str,
    source_snapshot: str,
    row_count: int,
    call_status: str,
    request_params_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "api": api,
        "source_snapshot": source_snapshot,
        "request_params_safe": request_params_safe or {},
        "row_count": int(row_count),
        "data_date": None,
        "local_fetched_at": _now_iso(),
        "call_status": call_status,
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _candidate_freshness_state(snapshot_map: Mapping[str, Any]) -> dict[str, Any]:
    data_freshness = _as_dict(snapshot_map.get("data_freshness"))
    source = "data_freshness" if data_freshness else "missing"
    state = (
        data_freshness.get("state")
        or data_freshness.get("status")
        or data_freshness.get("freshness_status")
        or "unknown"
    )
    return {
        "source": source,
        "state": state,
        "expected_trade_date": data_freshness.get("expected_trade_date")
        or data_freshness.get("expected_data_date")
        or data_freshness.get("expected_date"),
        "data_date": data_freshness.get("data_date") or data_freshness.get("trade_date"),
        "last_updated": data_freshness.get("last_updated") or data_freshness.get("updated_at"),
        "stale_inputs_are_reported_only": True,
        "enters_current_evidence": False,
        "does_not_modify_strategy_action": True,
    }


def _candidate_data_freshness_contract(freshness_state: Mapping[str, Any]) -> dict[str, Any]:
    state = str(freshness_state.get("state") or "unknown")
    expected_trade_date = freshness_state.get("expected_trade_date")
    data_date = freshness_state.get("data_date")
    if not data_date and expected_trade_date and state.lower() in {"fresh", "today"}:
        data_date = expected_trade_date
    if state.lower() == "today":
        state = "fresh"
    return {
        "schema_version": "candidate_radar_data_freshness.v1",
        "state": state,
        "freshness_state": state,
        "source": freshness_state.get("source") or "missing",
        "expected_trade_date": expected_trade_date,
        "expected_data_date": expected_trade_date,
        "data_date": data_date,
        "latest_data_date": data_date,
        "last_updated": freshness_state.get("last_updated"),
        "current_evidence_requires_expected_trade_date": True,
        "stale_inputs_are_research_only": True,
        "enters_current_evidence": False,
        "context_source": "candidate_radar_snapshot_freshness_state",
        "is_provider_acceptance": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _rows_from_any(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key in ("rows", "items", "providers", "capabilities", "data", "records"):
            nested = value.get(key)
            if isinstance(nested, list):
                rows.extend(_rows_from_any(nested))
        if not rows and any(key in value for key in ("provider", "api", "capability_state", "status", "state", "label")):
            rows.append(dict(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                rows.extend(_rows_from_any(item))
    return rows[:120]


def _provider_capability_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_key in (
        "data_health_ledger",
        "command_center_data_health_ledger",
        "a_share_capability_matrix",
        "provider_data_capability_cockpit",
        "provider_recovery_matrix",
        "data_gap_report",
    ):
        for row in _rows_from_any(snapshot_map.get(source_key)):
            safe = _safe_value(row)
            if not isinstance(safe, dict):
                continue
            safe.setdefault("source_key", source_key)
            rows.append(safe)
    return rows[:160]


def _provider_row_api_text(row: Mapping[str, Any]) -> str:
    values = [
        row.get("api"),
        row.get("interface"),
        row.get("section"),
        row.get("fact_key"),
        row.get("group"),
        row.get("label"),
        row.get("name"),
    ]
    return " ".join(str(value or "").lower() for value in values)


def _provider_status_text(row: Mapping[str, Any]) -> str:
    values = [
        row.get("capability_state"),
        row.get("status"),
        row.get("state"),
        row.get("readiness"),
        row.get("call_status"),
        row.get("validation_status"),
        row.get("error"),
        row.get("message"),
    ]
    return " ".join(str(value or "").lower() for value in values)


def _classify_provider_status(row: Mapping[str, Any]) -> str:
    status_text = _provider_status_text(row)
    if any(marker.lower() in status_text for marker in PROVIDER_BLOCKED_MARKERS):
        return "provider_blocked"
    if any(marker.lower() in status_text for marker in PROVIDER_STALE_MARKERS):
        return "stale_input"
    if any(marker.lower() in status_text for marker in PROVIDER_MISSING_MARKERS):
        return "missing_provider_data"
    if any(marker.lower() in status_text for marker in PROVIDER_AVAILABLE_MARKERS):
        return "available"
    return "unknown"


def _provider_coverage_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    capability_rows = _provider_capability_rows(snapshot_map)
    coverage_rows: list[dict[str, Any]] = []
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        apis = [str(api).lower() for api in requirement["apis"]]
        matched = [row for row in capability_rows if any(api in _provider_row_api_text(row) for api in apis)]
        classifications = [_classify_provider_status(row) for row in matched]
        if not matched:
            coverage_status = "missing_provider_data"
            severity = "coverage_gap"
        elif "provider_blocked" in classifications:
            coverage_status = "provider_blocked"
            severity = "provider_blocked"
        elif "stale_input" in classifications:
            coverage_status = "stale_input"
            severity = "freshness_gap"
        elif "missing_provider_data" in classifications:
            coverage_status = "missing_provider_data"
            severity = "coverage_gap"
        elif "available" in classifications:
            coverage_status = "available"
            severity = "ok"
        else:
            coverage_status = "unknown"
            severity = "coverage_unknown"
        coverage_rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "matched_provider_row_count": len(matched),
                "coverage_status": coverage_status,
                "severity": severity,
                "source_keys": sorted({str(row.get("source_key") or "") for row in matched if row.get("source_key")}),
                "matched_apis": sorted(
                    {
                        str(row.get("api") or row.get("interface") or row.get("section") or "")
                        for row in matched
                        if row.get("api") or row.get("interface") or row.get("section")
                    }
                ),
                "reported_as_gap": coverage_status != "available",
                "does_not_refresh_provider": True,
                "does_not_call_external_sources": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    return coverage_rows


def _degraded_mode_rows(
    *,
    scan_mode: str,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "mode": "local_cache_only",
            "active": True,
            "severity": "info",
            "reason": "radar_scan_reads_local_snapshot_without_provider_refresh",
            "user_visible": True,
            "does_not_call_external_sources": True,
        },
        {
            "mode": "full_pool_scan_pending",
            "active": scan_mode != "full_pool_scan",
            "severity": "future_task",
            "reason": "full_pool_scan_requires_future_worker_task",
            "user_visible": True,
            "does_not_scan_full_market_on_render": True,
        },
    ]
    status_counts = {
        "provider_blocked": sum(1 for row in provider_rows if row.get("coverage_status") == "provider_blocked"),
        "stale_input": sum(1 for row in provider_rows if row.get("coverage_status") == "stale_input"),
        "missing_provider_data": sum(1 for row in provider_rows if row.get("coverage_status") == "missing_provider_data"),
    }
    for status, count in status_counts.items():
        rows.append(
            {
                "mode": status,
                "active": bool(count),
                "severity": "coverage_gap" if status != "stale_input" else "freshness_gap",
                "affected_group_count": count,
                "reason": f"{status}_reported_without_refresh",
                "user_visible": True,
                "does_not_call_external_sources": True,
            }
        )
    freshness = str(freshness_state.get("state") or "").lower()
    rows.append(
        {
            "mode": "freshness_research_only",
            "active": freshness_state.get("source") == "missing" or freshness in {"stale", "expired", "historical", "unknown"},
            "severity": "freshness_gap",
            "reason": "stale_or_missing_freshness_is_display_only",
            "user_visible": True,
            "does_not_modify_strategy_action": True,
        }
    )
    if local_pool_audit:
        rows.append(
            {
                "mode": "local_pool_partial",
                "active": bool(
                    local_pool_audit.get("duplicate_candidate_count")
                    or local_pool_audit.get("invalid_candidate_count")
                    or local_pool_audit.get("disabled_candidate_count")
                    or local_pool_audit.get("truncated_candidate_count")
                    or not candidate_rows
                ),
                "severity": "input_gap",
                "reason": "local_pool_skips_are_visible_and_do_not_trigger_broad_scan",
                "user_visible": True,
                "does_not_scan_full_market_on_render": True,
            }
        )
    return rows


def _skipped_reason_rows(
    *,
    source_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    freshness_state: Mapping[str, Any],
    provider_coverage_rows: list[dict[str, Any]] | None = None,
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
    candidate_input_count: int = 0,
    candidate_display_limit: int = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
    candidate_display_truncated_count: int = 0,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = list(local_pool_skipped_rows or [])
    audit = local_pool_audit or {}
    if audit and not audit.get("normalized_candidate_count"):
        rows.append(
            {
                "reason": "local_candidate_pool_empty",
                "group": audit.get("scan_mode") or "local_candidate_pool",
                "severity": "empty_result",
                "input_source": audit.get("input_source") or "missing",
                "action": "show_empty_state_do_not_scan_full_market",
            }
        )
    for row in source_rows:
        if row.get("present"):
            continue
        rows.append(
            {
                "reason": "legacy_signal_group_missing_in_snapshot",
                "group": row.get("group"),
                "severity": "coverage_gap",
                "action": "report_gap_do_not_silently_drop",
            }
        )
    for row in provider_coverage_rows or []:
        status = str(row.get("coverage_status") or "")
        if status == "available":
            continue
        reason = {
            "provider_blocked": "radar_provider_blocked",
            "stale_input": "radar_provider_stale_input",
            "missing_provider_data": "radar_provider_missing_data",
        }.get(status, "radar_provider_unknown")
        rows.append(
            {
                "reason": reason,
                "group": row.get("signal_group"),
                "severity": row.get("severity") or "coverage_gap",
                "matched_provider_row_count": row.get("matched_provider_row_count"),
                "action": "report_provider_gap_do_not_refresh_on_render",
            }
        )
    if not candidate_rows:
        rows.append(
            {
                "reason": "no_candidate_rows_in_cache",
                "group": "next_ticket_candidates",
                "severity": "empty_result",
                "action": "show_empty_state_do_not_scan_full_market",
            }
        )
    if excluded_candidates:
        rows.append(
            {
                "reason": "excluded_candidates_present",
                "group": "radar_packet.excluded_candidates",
                "severity": "info",
                "action": "display_exclusions_without_trade_instruction",
                "row_count": len(excluded_candidates),
            }
        )
    if candidate_display_truncated_count:
        rows.append(
            {
                "reason": "candidate_rows_display_capped",
                "group": "next_ticket_candidates",
                "severity": "ui_runtime_budget",
                "input_candidate_count": candidate_input_count,
                "display_limit": candidate_display_limit,
                "truncated_candidate_count": candidate_display_truncated_count,
                "action": "show_runtime_budget_contract_and_require_worker_for_large_universe",
            }
        )
    if freshness_state.get("source") == "missing":
        rows.append(
            {
                "reason": "data_freshness_missing",
                "group": "data_freshness",
                "severity": "freshness_unknown",
                "action": "report_unknown_freshness_as_research_only",
            }
        )
    elif str(freshness_state.get("state") or "").lower() in {"stale", "expired", "historical", "unknown"}:
        rows.append(
            {
                "reason": "data_freshness_not_current",
                "group": "data_freshness",
                "severity": "freshness_gap",
                "state": freshness_state.get("state"),
                "action": "report_stale_inputs_without_action_mutation",
            }
        )
    return rows


def _scan_coverage(
    *,
    snapshot_available: bool,
    snapshot_map: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    scan_mode: str,
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
    candidate_input_count: int = 0,
    candidate_display_truncated_count: int = 0,
) -> dict[str, Any]:
    source_rows = _source_group_rows(snapshot_map)
    present = [row for row in source_rows if row["present"]]
    missing = [str(row["group"]) for row in source_rows if not row["present"]]
    freshness_state = _candidate_freshness_state(snapshot_map)
    provider_rows = _provider_coverage_rows(snapshot_map)
    skipped_rows = _skipped_reason_rows(
        source_rows=source_rows,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        freshness_state=freshness_state,
        provider_coverage_rows=provider_rows,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        candidate_input_count=candidate_input_count,
        candidate_display_limit=FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        candidate_display_truncated_count=candidate_display_truncated_count,
    )
    audit = local_pool_audit or {}
    universe_mode = (
        "local_watchlist"
        if scan_mode == "watchlist_scan"
        else "manual_input"
        if scan_mode == "custom_pool_scan"
        else "single_symbol_search"
        if scan_mode == QUANT_PROJECTION_SCAN_MODE
        else "cache_snapshot"
    )
    universe_size = (
        audit.get("input_candidate_count")
        if audit.get("input_candidate_count") is not None
        else candidate_input_count + len(excluded_candidates)
    )
    degraded_rows = _degraded_mode_rows(
        scan_mode=scan_mode,
        provider_rows=provider_rows,
        freshness_state=freshness_state,
        local_pool_audit=audit,
        candidate_rows=candidate_rows,
    )
    provider_blocked_count = sum(1 for row in provider_rows if row.get("coverage_status") == "provider_blocked")
    stale_input_count = sum(1 for row in provider_rows if row.get("coverage_status") == "stale_input")
    missing_provider_count = sum(1 for row in provider_rows if row.get("coverage_status") == "missing_provider_data")
    degraded_active_count = sum(1 for row in degraded_rows if row.get("active"))
    coverage_detail_summary = {
        "scan_mode": scan_mode,
        "universe_mode": universe_mode,
        "universe_size": int(universe_size or 0),
        "candidate_input_count": int(candidate_input_count or 0),
        "candidate_count": len(candidate_rows),
        "candidate_display_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "candidate_display_truncated_count": int(candidate_display_truncated_count or 0),
        "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
        "excluded_candidate_count": len(excluded_candidates),
        "provider_signal_group_count": len(provider_rows),
        "provider_blocked_group_count": provider_blocked_count,
        "stale_input_group_count": stale_input_count,
        "missing_provider_data_group_count": missing_provider_count,
        "degraded_mode_count": len(degraded_rows),
        "degraded_mode_active_count": degraded_active_count,
        "degraded_mode_active": bool(degraded_active_count),
        "quick_scan_is_research_only": True,
        "full_pool_scan_done": False,
        "full_pool_scan_requires_worker": True,
        "missing_data_is_reported_not_dropped": True,
        "large_universe_requires_worker": int(universe_size or 0) > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "does_not_call_external_sources": True,
        "does_not_scan_full_market_on_render": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    return {
        "scan_mode": scan_mode,
        "scan_scope": "local_snapshot_cache_only",
        "snapshot_available": snapshot_available,
        "universe_mode": universe_mode,
        "universe_size": int(universe_size or 0),
        "candidate_input_count": int(candidate_input_count or 0),
        "candidate_display_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "candidate_display_truncated_count": int(candidate_display_truncated_count or 0),
        "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
        "legacy_signal_group_count": len(source_rows),
        "mapped_signal_group_count": len(present),
        "missing_signal_group_count": len(missing),
        "missing_signal_groups": missing,
        "legacy_signal_group_rows": source_rows,
        "provider_signal_group_count": len(provider_rows),
        "provider_blocked_group_count": provider_blocked_count,
        "stale_input_group_count": stale_input_count,
        "missing_provider_data_group_count": missing_provider_count,
        "provider_coverage_rows": provider_rows,
        "degraded_mode_rows": degraded_rows,
        "coverage_detail_summary": coverage_detail_summary,
        "candidate_count": len(candidate_rows),
        "local_pool_input_candidate_count": audit.get("input_candidate_count"),
        "local_pool_normalized_candidate_count": audit.get("normalized_candidate_count"),
        "local_pool_duplicate_candidate_count": audit.get("duplicate_candidate_count"),
        "local_pool_invalid_candidate_count": audit.get("invalid_candidate_count"),
        "local_pool_disabled_candidate_count": audit.get("disabled_candidate_count"),
        "local_pool_truncated_candidate_count": audit.get("truncated_candidate_count"),
        "excluded_candidate_count": len(excluded_candidates),
        "skipped_reason_count": len(skipped_rows),
        "skipped_reason_rows": skipped_rows,
        "freshness_state": freshness_state,
        "coverage_status": "ready" if candidate_rows else ("partial_no_candidates" if present else "cache_missing"),
        "feature_loss_guard": "Missing legacy radar groups are reported as coverage gaps; they are not silently dropped.",
        "quick_scan_reads_cache_only": True,
        "large_universe_requires_worker": int(universe_size or 0) > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "watchlist_scan_reads_local_input_only": scan_mode == "watchlist_scan",
        "custom_pool_scan_reads_local_input_only": scan_mode == "custom_pool_scan",
        "does_not_scan_full_market_on_render": True,
        "does_not_call_external_sources": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _scan_execution_summary(
    *,
    mode: str,
    cache_source: str,
    scan_mode: str,
    request_params_safe: Mapping[str, Any],
    coverage: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    scan_family = (
        "full_pool_plan"
        if scan_mode == "full_pool_plan"
        else "full_pool_local_execution"
        if scan_mode == "full_pool_local_scan"
        else "deep_scan_plan"
        if scan_mode == "deep_scan_plan"
        else "deep_scan_local_review"
        if scan_mode == "deep_scan_local_review"
        else "search_quant_projection"
        if scan_mode == QUANT_PROJECTION_SCAN_MODE
        else "local_pool_scan"
        if scan_mode in LOCAL_POOL_SCAN_MODES
        else "quick_cache_scan"
        if scan_mode == "quick_cache_scan"
        else "cache_view"
    )
    return {
        "schema_version": "candidate_radar_scan_execution_summary.v1",
        "mode": mode,
        "scan_mode": scan_mode,
        "scan_family": scan_family,
        "cache_source": cache_source,
        "requested_scan_mode": request_params_safe.get("requested_scan_mode") or request_params_safe.get("scan_mode") or scan_mode,
        "unsupported_scan_mode_fallback": bool(request_params_safe.get("unsupported_scan_mode_fallback")),
        "universe_mode": coverage_detail.get("universe_mode") or request_params_safe.get("universe_mode") or coverage.get("universe_mode"),
        "universe_size": int(coverage_detail.get("universe_size") or coverage.get("universe_size") or 0),
        "candidate_input_count": int(coverage_detail.get("candidate_input_count") or 0),
        "candidate_row_count": len(candidate_rows),
        "candidate_display_limit": int(coverage_detail.get("candidate_display_limit") or FAST_SCAN_DISPLAY_CANDIDATE_LIMIT),
        "candidate_display_truncated_count": int(coverage_detail.get("candidate_display_truncated_count") or 0),
        "candidate_rows_capped_for_ui": bool(coverage_detail.get("candidate_rows_capped_for_ui")),
        "skipped_reason_count": int(coverage.get("skipped_reason_count") or 0),
        "provider_gap_count": provider_gap_count,
        "degraded_mode_active_count": int(coverage_detail.get("degraded_mode_active_count") or 0),
        "freshness_state": freshness_state.get("state") or "unknown",
        "freshness_source": freshness_state.get("source") or "missing",
        "local_pool_input_candidate_count": local_pool_audit.get("input_candidate_count"),
        "local_pool_normalized_candidate_count": local_pool_audit.get("normalized_candidate_count"),
        "full_pool_plan_ready": full_pool_scan_plan.get("status") == "full_pool_plan_ready",
        "full_pool_scan_done": bool(full_pool_scan_plan.get("full_pool_scan_done") is True),
        "full_pool_blocking_issue_count": full_pool_scan_plan.get("blocking_issue_count"),
        "deep_scan_plan_ready": deep_scan_plan.get("status") == "deep_scan_plan_ready",
        "deep_scan_done": bool(deep_scan_plan.get("deep_scan_done") is True),
        "deep_scan_blocking_issue_count": deep_scan_plan.get("blocking_issue_count"),
        "writes_sqlite_packet": mode != "cache_only",
        "cache_view_only": mode == "cache_only",
        "result_is_research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _scan_acceptance_rows(
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    full_pool_plan_ready = full_pool_scan_plan.get("status") == "full_pool_plan_ready"
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_ok = freshness_state.get("source") != "missing" and str(freshness_state.get("state") or "").lower() not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    deep_scan_plan_ready = deep_scan_plan.get("status") == "deep_scan_plan_ready"
    rows = [
        {
            "check_key": "page_render_does_not_scan",
            "status": "passed",
            "observed": "GET cache and React render are read-only.",
            "user_visible": True,
        },
        {
            "check_key": "external_call_boundary",
            "status": "passed",
            "observed": "No Tushare, DeepSeek, or GitHub call is made by this radar packet.",
            "user_visible": True,
        },
        {
            "check_key": "scan_mode_contract",
            "status": "passed"
            if scan_mode in SUPPORTED_LOCAL_SCAN_MODES
            or scan_mode in {"cache_only", "full_pool_plan", "deep_scan_local_review", QUANT_PROJECTION_SCAN_MODE}
            else "fallback_reported",
            "observed": scan_mode,
            "user_visible": True,
        },
        {
            "check_key": "candidate_result_boundary",
            "status": "ready" if candidate_rows else "empty_reported",
            "observed": f"{len(candidate_rows)} candidate rows; result remains research-only.",
            "user_visible": True,
        },
        {
            "check_key": "provider_gap_visibility",
            "status": "gap_reported" if provider_gap_count else "passed",
            "observed": f"{provider_gap_count} provider gaps reported without refresh.",
            "user_visible": True,
        },
        {
            "check_key": "freshness_boundary",
            "status": "passed" if freshness_ok else "research_only_reported",
            "observed": f"{freshness_state.get('source') or 'missing'}:{freshness_state.get('state') or 'unknown'}",
            "user_visible": True,
        },
        {
            "check_key": "local_pool_boundary",
            "status": "input_reported" if local_pool_audit else "not_applicable",
            "observed": f"input={local_pool_audit.get('input_candidate_count')} normalized={local_pool_audit.get('normalized_candidate_count')}"
            if local_pool_audit
            else "quick cache or full-pool plan does not consume local pool input.",
            "user_visible": True,
        },
        {
            "check_key": "full_pool_boundary",
            "status": "local_execution_receipt" if scan_mode == "full_pool_local_scan" else "plan_only" if full_pool_plan_ready else "not_executed",
            "observed": (
                "local_full_pool_execution_done=true; production_full_pool_scan_done=false; provider_refresh_executed=false."
                if scan_mode == "full_pool_local_scan"
                else "full_pool_scan_done=false; plan does not score candidates or refresh providers."
            ),
            "user_visible": True,
        },
        {
            "check_key": "deep_scan_boundary",
            "status": "local_review_receipt"
            if scan_mode == "deep_scan_local_review"
            else "plan_only"
            if deep_scan_plan_ready
            else "not_executed",
            "observed": (
                "local_deep_scan_review_done=true; deep_scan_done=false; deepseek_called=false; provider_refresh_executed=false."
                if scan_mode == "deep_scan_local_review"
                else "deep_scan_done=false; plan records no-feature-loss readiness and does not call providers or DeepSeek."
            ),
            "user_visible": True,
        },
        {
            "check_key": "feature_loss_boundary",
            "status": "gap_reported"
            if int(deep_scan_plan.get("legacy_feature_gap_count") or 0)
            else "passed"
            if deep_scan_plan_ready
            else "not_executed",
            "observed": f"{deep_scan_plan.get('legacy_feature_gap_count') or 0} legacy feature gaps visible.",
            "user_visible": True,
        },
        {
            "check_key": "trade_action_boundary",
            "status": "passed",
            "observed": "Radar candidates do not modify strategy action, holdings, or execute trades.",
            "user_visible": True,
        },
    ]
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    return rows


def _runtime_budget_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    user_visible: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "user_visible": user_visible,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _fast_scan_runtime_budget_contract(
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    universe_size = int(coverage_detail.get("universe_size") or 0)
    input_count = int(coverage_detail.get("candidate_input_count") or 0)
    truncated_count = int(coverage_detail.get("candidate_display_truncated_count") or 0)
    local_pool_input_count = local_pool_audit.get("input_candidate_count")
    local_pool_truncated_count = int(local_pool_audit.get("truncated_candidate_count") or 0)
    worker_required = universe_size > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD or local_pool_truncated_count > 0
    rows = [
        _runtime_budget_row(
            "page_render_zero_scan_budget",
            "passed",
            passed=True,
            evidence="React render and GET cache do not start candidate scans or provider refresh.",
        ),
        _runtime_budget_row(
            "sync_candidate_display_budget",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            evidence=f"input={input_count}; displayed={len(candidate_rows)}; limit={FAST_SCAN_DISPLAY_CANDIDATE_LIMIT}; truncated={truncated_count}",
        ),
        _runtime_budget_row(
            "local_pool_sync_input_budget",
            "capped_visible" if local_pool_truncated_count else "passed",
            passed=True,
            evidence=f"input={local_pool_input_count}; limit={FAST_SCAN_LOCAL_POOL_INPUT_LIMIT}; truncated={local_pool_truncated_count}",
        ),
        _runtime_budget_row(
            "large_universe_worker_boundary",
            "worker_required" if worker_required else "not_required",
            passed=True,
            evidence=f"universe_size={universe_size}; threshold={FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD}",
        ),
        _runtime_budget_row(
            "feature_gap_visibility_budget",
            "passed",
            passed=True,
            evidence="Candidate display caps, provider gaps, stale inputs, and missing legacy groups are reported as rows instead of being hidden.",
        ),
    ]
    return {
        "schema_version": "candidate_radar_fast_scan_runtime_budget.v1",
        "status": "fast_scan_runtime_budget_ready",
        "scope": "local_sync_budget_contract_not_browser_performance_trace",
        "scan_mode": scan_mode,
        "display_candidate_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "local_pool_input_limit": FAST_SCAN_LOCAL_POOL_INPUT_LIMIT,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "candidate_input_count": input_count,
        "candidate_displayed_count": len(candidate_rows),
        "candidate_display_truncated_count": truncated_count,
        "candidate_rows_capped_for_ui": bool(truncated_count),
        "local_pool_input_candidate_count": local_pool_input_count,
        "local_pool_truncated_candidate_count": local_pool_truncated_count,
        "large_universe_worker_required": worker_required,
        "browser_performance_trace_done": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "feature_gaps_visible": True,
        "cache_get_starts_scan": False,
        "page_render_starts_scan": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "This is a static runtime-budget contract for local quick/watchlist/custom scans; browser performance traces and real full-pool worker execution remain future validation.",
    }


def _quick_scan_receipt_row(
    receipt_key: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "receipt_key": receipt_key,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_blocker": bool(production_blocker),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _task_pipeline_contract_row(
    criterion: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_blocker": bool(production_blocker),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _fast_scan_task_pipeline_contract(packet: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scan_summary = _as_dict(packet.get("scan_execution_summary"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    quick_receipt = _as_dict(packet.get("quick_scan_execution_receipt"))
    scan_mode = str(packet.get("scan_mode") or scan_summary.get("scan_mode") or "cache_only")
    task_id = str(packet.get("task_id") or "")
    cache_view_only = scan_summary.get("cache_view_only") is True
    writes_sqlite_packet = scan_summary.get("writes_sqlite_packet") is True
    task_id_visible = cache_view_only or writes_sqlite_packet or bool(task_id)
    previous_diff_visible = result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1"
    rows = [
        _task_pipeline_contract_row(
            "initial_cache_render_nonblocking",
            "passed",
            local_contract_passed=True,
            production_blocker=False,
            evidence="GET cache and initial React render read cache first; page render does not start radar scans.",
            next_action="Keep Candidate Radar render path cache-only; create scans only from POST task buttons or explicit live_light task.",
        ),
        _task_pipeline_contract_row(
            "post_task_boundary_visible",
            "cache_view_waiting_for_post" if cache_view_only else "passed_post_task",
            local_contract_passed=cache_view_only or writes_sqlite_packet,
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; writes_sqlite_packet={writes_sqlite_packet}; cache_view_only={cache_view_only}",
            next_action="Keep quick/watchlist/custom/full-pool-local scans behind explicit POST task boundaries.",
        ),
        _task_pipeline_contract_row(
            "task_id_status_visible",
            "cache_view_uses_last_packet"
            if cache_view_only
            else "passed_task_id_visible"
            if task_id
            else "task_envelope_required"
            if writes_sqlite_packet
            else "missing_task_id",
            local_contract_passed=task_id_visible,
            production_blocker=not task_id_visible,
            evidence=f"task_id_present={bool(task_id)}; scan_family={scan_summary.get('scan_family') or 'missing'}",
            next_action="Surface task_id through TaskLaunchReceipt and TaskStatusPanel so scans do not block the page.",
        ),
        _task_pipeline_contract_row(
            "last_success_cache_fallback_visible",
            "previous_cache_diff_visible" if result_delta.get("previous_cache_diff_done") is True else "fallback_path_visible",
            local_contract_passed=previous_diff_visible,
            production_blocker=False,
            evidence=f"previous_cache_available={result_delta.get('previous_cache_available')}; previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}",
            next_action="Keep the previous-cache diff or pending state visible while a new scan runs, fails, or returns empty.",
        ),
        _task_pipeline_contract_row(
            "safe_failure_boundary_visible",
            "passed_safe_error_path",
            local_contract_passed=packet.get("external_calls_triggered") is False
            and packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            production_blocker=False,
            evidence="Storage-write failures return error_message_safe on the task and never trigger provider/model/trade work.",
            next_action="Keep task failure as a local safe error; do not refresh providers or mutate action from failure recovery.",
        ),
        _task_pipeline_contract_row(
            "input_budget_worker_boundary_visible",
            "worker_required" if runtime_budget.get("large_universe_worker_required") is True else "passed_budget_visible",
            local_contract_passed=runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1",
            production_blocker=False,
            evidence=f"display_limit={runtime_budget.get('display_candidate_limit')}; local_pool_limit={runtime_budget.get('local_pool_input_limit')}; worker_threshold={runtime_budget.get('worker_required_universe_threshold')}",
            next_action="Keep sync display caps visible; move large universe/deep work to worker-backed tasks before production replacement.",
        ),
        _task_pipeline_contract_row(
            "no_feature_loss_gap_visibility",
            "gap_reported" if int(coverage.get("missing_signal_group_count") or 0) else "passed",
            local_contract_passed=coverage_detail.get("missing_data_is_reported_not_dropped") is True
            or bool(coverage.get("legacy_signal_group_rows")),
            production_blocker=int(coverage.get("missing_signal_group_count") or 0) > 0,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing={coverage.get('missing_signal_group_count')}; skipped={coverage.get('skipped_reason_count')}",
            next_action="Preserve old radar signal groups as visible rows; do not treat gap_reported as feature parity completion.",
        ),
        _task_pipeline_contract_row(
            "production_replacement_stays_blocked",
            "pending_worker_provider_browser_acceptance",
            local_contract_passed=quick_receipt.get("production_radar_replacement_complete") is False
            and quick_receipt.get("provider_backed_acceptance_done") is False,
            production_blocker=True,
            evidence=f"full_pool_scan_done={quick_receipt.get('full_pool_scan_done')}; deep_scan_done={quick_receipt.get('deep_scan_done')}; provider_backed_acceptance_done={quick_receipt.get('provider_backed_acceptance_done')}",
            next_action="Require worker full/deep execution, provider-backed parity, browser QA, and legacy retirement review before production replacement.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    contract = {
        "schema_version": "candidate_radar_fast_scan_task_pipeline.v1",
        "status": "fast_scan_task_pipeline_ready_local_only" if not local_blockers else "fast_scan_task_pipeline_blocked",
        "scope": "local_candidate_radar_task_pipeline_not_async_worker_or_provider_execution",
        "ltg": "LTG-13",
        "scan_mode": scan_mode,
        "scan_family": scan_summary.get("scan_family"),
        "cache_source": packet.get("cache_source") or scan_summary.get("cache_source"),
        "task_id": task_id,
        "task_id_visible": task_id_visible,
        "cache_view_only": cache_view_only,
        "writes_sqlite_packet": writes_sqlite_packet,
        "post_task_boundary_visible": cache_view_only or writes_sqlite_packet,
        "initial_render_nonblocking": True,
        "task_status_panel_required": True,
        "last_success_cache_fallback_visible": previous_diff_visible,
        "safe_failure_boundary_visible": True,
        "input_budget_worker_boundary_visible": runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1",
        "no_feature_loss_gap_visibility": True,
        "local_task_pipeline_ready": not local_blockers,
        "async_worker_execution_done": False,
        "provider_backed_acceptance_done": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "browser_performance_trace_done": False,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This contract proves the local task pipeline shape for fast Candidate Radar scans: render first, explicit POST task, visible task status, local cache fallback, input budgets, visible gaps, and no provider/model/trade work. It is not async worker execution, provider-backed parity, browser performance proof, or production replacement.",
    }
    return contract, rows


def _quick_scan_receipt_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    scan_summary = _as_dict(packet.get("scan_execution_summary"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    local_pool = _as_dict(packet.get("local_candidate_pool_audit"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    call_ledger = _as_list(packet.get("call_ledger"))
    candidate_rows = _as_list(packet.get("candidate_rows"))
    scan_mode = str(packet.get("scan_mode") or scan_summary.get("scan_mode") or "cache_only")
    freshness_state = str(freshness.get("state") or scan_summary.get("freshness_state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    provider_gap_count = int(scan_summary.get("provider_gap_count") or 0)
    if not provider_gap_count:
        provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
            coverage_detail.get("stale_input_group_count") or 0
        ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    legacy_gap_count = int(coverage.get("missing_signal_group_count") or parity.get("gap_or_future_count") or 0)
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True or scan_summary.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True or scan_summary.get("deep_scan_done") is True)
    local_pool_input_count = local_pool.get("input_candidate_count")
    local_pool_truncated_count = int(local_pool.get("truncated_candidate_count") or 0)
    return [
        _quick_scan_receipt_row(
            "scan_mode_visible",
            "passed" if scan_mode else "missing",
            local_contract_passed=bool(scan_mode),
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; scan_family={scan_summary.get('scan_family') or 'missing'}",
            next_action="Keep scan mode and scan family visible before interpreting candidate rows.",
        ),
        _quick_scan_receipt_row(
            "task_or_cache_receipt_visible",
            "passed" if scan_summary and call_ledger else "missing_receipt",
            local_contract_passed=bool(scan_summary and call_ledger),
            production_blocker=False,
            evidence=f"call_ledger_count={len(call_ledger)}; writes_sqlite_packet={scan_summary.get('writes_sqlite_packet')}",
            next_action="Use the visible call ledger and scan summary as the local receipt for cache reads or button-gated scans.",
        ),
        _quick_scan_receipt_row(
            "candidate_count_visible",
            "passed",
            local_contract_passed=True,
            production_blocker=False,
            evidence=f"candidate_rows={len(candidate_rows)}; input={scan_summary.get('candidate_input_count')}; display_limit={scan_summary.get('candidate_display_limit')}; truncated={scan_summary.get('candidate_display_truncated_count')}",
            next_action="Keep displayed count, input count, display limit, and truncation visible to avoid hiding scan shrinkage.",
        ),
        _quick_scan_receipt_row(
            "runtime_budget_visible",
            "passed" if runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1" else "missing",
            local_contract_passed=runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1",
            production_blocker=False,
            evidence=f"large_universe_worker_required={runtime_budget.get('large_universe_worker_required')}; browser_performance_trace_done={runtime_budget.get('browser_performance_trace_done')}",
            next_action="Keep sync display caps and worker boundary visible; run browser traces before production replacement.",
        ),
        _quick_scan_receipt_row(
            "legacy_signal_coverage_visible",
            "gap_reported" if legacy_gap_count else "passed",
            local_contract_passed=True,
            production_blocker=legacy_gap_count > 0,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing_or_future={legacy_gap_count}",
            next_action="Map remaining legacy signal groups or keep fallback visible before claiming no feature loss.",
        ),
        _quick_scan_receipt_row(
            "provider_gap_visible",
            "gap_reported" if provider_gap_count else "passed",
            local_contract_passed=True,
            production_blocker=provider_gap_count > 0,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate provider-backed parity through explicit future tasks; do not refresh providers on render.",
        ),
        _quick_scan_receipt_row(
            "freshness_boundary_visible",
            "passed" if freshness_ready else "research_only_reported",
            local_contract_passed=True,
            production_blocker=not freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness_state}",
            next_action="Require trading-calendar freshness before treating radar rows as current evidence.",
        ),
        _quick_scan_receipt_row(
            "local_pool_limit_visible",
            "capped_visible" if local_pool_truncated_count else "passed" if local_pool else "not_applicable",
            local_contract_passed=True,
            production_blocker=False,
            evidence=f"local_pool_input={local_pool_input_count}; truncated={local_pool_truncated_count}; input_limit={FAST_SCAN_LOCAL_POOL_INPUT_LIMIT}",
            next_action="Keep watchlist/custom-pool normalization and truncation visible for non-blocking local scans.",
        ),
        _quick_scan_receipt_row(
            "result_delta_visible",
            "passed" if result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1" else "missing",
            local_contract_passed=result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1",
            production_blocker=False,
            evidence=f"previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}; browser_visual_delta_qa_done={result_delta.get('browser_visual_delta_qa_done')}",
            next_action="Keep previous-cache diff visible when available; browser visual QA remains a separate acceptance step.",
        ),
        _quick_scan_receipt_row(
            "full_deep_provider_blockers_visible",
            "pending_production_acceptance" if not (full_pool_done and deep_scan_done and provider_gap_count == 0) else "passed",
            local_contract_passed=True,
            production_blocker=not (full_pool_done and deep_scan_done and provider_gap_count == 0),
            evidence=f"full_pool_scan_done={full_pool_done}; deep_scan_done={deep_scan_done}; provider_gap_count={provider_gap_count}",
            next_action="Complete worker-backed full-pool/deep-scan and provider-backed acceptance before retiring legacy radar.",
        ),
        _quick_scan_receipt_row(
            "trade_action_isolation",
            "passed"
            if packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True
            else "blocked",
            local_contract_passed=packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            production_blocker=False,
            evidence="Candidate radar remains research-only and does not mutate action, holdings, or orders.",
            next_action="Keep radar candidates separate from strategy action and real-trading paths.",
        ),
    ]


def _attach_quick_scan_receipt_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _quick_scan_receipt_rows(view)
    local_blockers = [row["receipt_key"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["receipt_key"] for row in rows if row.get("production_blocker")]
    scan_summary = _as_dict(view.get("scan_execution_summary"))
    coverage_detail = _as_dict(view.get("coverage_detail_summary"))
    local_pool = _as_dict(view.get("local_candidate_pool_audit"))
    freshness = _as_dict(view.get("freshness_state"))
    contract = {
        "schema_version": "candidate_radar_quick_scan_receipt.v1",
        "status": "quick_scan_receipt_ready_local_only" if not local_blockers else "quick_scan_receipt_blocked",
        "scope": "local_candidate_radar_quick_scan_receipt_not_production_replacement",
        "ltg": "LTG-13",
        "scan_mode": view.get("scan_mode") or scan_summary.get("scan_mode"),
        "scan_family": scan_summary.get("scan_family"),
        "cache_source": view.get("cache_source") or scan_summary.get("cache_source"),
        "requested_scan_mode": scan_summary.get("requested_scan_mode"),
        "unsupported_scan_mode_fallback": bool(scan_summary.get("unsupported_scan_mode_fallback")),
        "candidate_input_count": int(scan_summary.get("candidate_input_count") or coverage_detail.get("candidate_input_count") or 0),
        "candidate_row_count": len(_as_list(view.get("candidate_rows"))),
        "candidate_display_limit": int(
            scan_summary.get("candidate_display_limit") or coverage_detail.get("candidate_display_limit") or FAST_SCAN_DISPLAY_CANDIDATE_LIMIT
        ),
        "candidate_display_truncated_count": int(
            scan_summary.get("candidate_display_truncated_count")
            or coverage_detail.get("candidate_display_truncated_count")
            or 0
        ),
        "local_pool_input_candidate_count": local_pool.get("input_candidate_count"),
        "local_pool_truncated_candidate_count": int(local_pool.get("truncated_candidate_count") or 0),
        "mapped_signal_group_count": int(_as_dict(view.get("scan_coverage")).get("mapped_signal_group_count") or 0),
        "missing_signal_group_count": int(_as_dict(view.get("scan_coverage")).get("missing_signal_group_count") or 0),
        "provider_gap_count": int(scan_summary.get("provider_gap_count") or 0),
        "degraded_mode_active_count": int(scan_summary.get("degraded_mode_active_count") or 0),
        "freshness_state": freshness.get("state") or scan_summary.get("freshness_state") or "unknown",
        "freshness_source": freshness.get("source") or scan_summary.get("freshness_source") or "missing",
        "writes_sqlite_packet": bool(scan_summary.get("writes_sqlite_packet") is True),
        "cache_view_only": bool(scan_summary.get("cache_view_only") is True),
        "local_quick_scan_receipt_ready": not local_blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This receipt is local/cache-only. It makes fast-scan coverage, limits, gaps, and blockers visible; it is not full-pool, deep-scan, provider-backed, browser-performance, or production replacement evidence.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["quick_scan_receipt_row_count"] = contract["row_count"]
    counts["quick_scan_receipt_local_blocker_count"] = contract["local_blocker_count"]
    counts["quick_scan_receipt_production_blocker_count"] = contract["production_blocker_count"]
    counts["quick_scan_receipt_provider_gap_count"] = contract["provider_gap_count"]
    counts["quick_scan_receipt_missing_signal_group_count"] = contract["missing_signal_group_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["quick_scan_receipt_contract_is_local"] = True
    policy["quick_scan_receipt_is_not_production_replacement"] = True
    policy["quick_scan_receipt_requires_full_deep_provider_browser_evidence"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["quick_scan_execution_receipt"] = contract
    view["quick_scan_execution_receipt_rows"] = rows
    return view


def _candidate_browser_qa_runbook_row(
    phase: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    required_before_completion: bool = True,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "required_before_completion": bool(required_before_completion),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_runbook_contract() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    runbook_source = _read_local_text(CANDIDATE_BROWSER_QA_RUNBOOK_PATH)
    runner_source = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    candidate_source = _read_local_text(CANDIDATE_ROUTE_SOURCE_PATH)
    viewports = [
        {"name": "desktop", "width": 1440, "height": 900},
        {"name": "laptop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 834, "height": 1112},
        {"name": "mobile", "width": 390, "height": 844},
    ]
    runner_available = (
        MOTION_BROWSER_QA_RUNNER_PATH.exists()
        and "command_center_3_motion_browser_qa_result.v1" in runner_source
        and "explicit_local_browser_visual_performance_run" in runner_source
        and "chromium.launch" in runner_source
        and "page.goto" in runner_source
        and "#candidates" in runner_source
        and "Candidate Radar" in runner_source
        and ".stock_ming_3/motion_qa" in runner_source
        and "starts_no_servers" in runner_source
        and "local_urls_only" in runner_source
        and "tushare_adapter" not in runner_source
        and "deepseek_adapter" not in runner_source
        and "api.github.com" not in runner_source
        and "place_order" not in runner_source
    )
    runbook_ready = (
        CANDIDATE_BROWSER_QA_RUNBOOK_PATH.exists()
        and "candidate_radar_browser_qa_runbook.v1" in runbook_source
        and "local_candidate_radar_browser_qa_runbook_not_browser_execution" in runbook_source
        and "#candidates" in runbook_source
        and ".stock_ming_3/motion_qa" in runbook_source
        and "opens_no_browser" in runbook_source
        and "writes_no_artifacts" in runbook_source
        and "visual_qa_complete" in runbook_source
        and "browser_performance_trace_done" in runbook_source
    )
    route_source_ready = (
        CANDIDATE_ROUTE_SOURCE_PATH.exists()
        and "radar-result-cluster" in candidate_source
        and "StateClarityRail" in candidate_source
        and "resultDeltaClarity" in candidate_source
        and "previousCacheDiffRows" in candidate_source
        and "postCandidateRadarQuickScan" in candidate_source
        and "postCandidateRadarFullPoolPlan" in candidate_source
        and "postCandidateRadarDeepScanPlan" in candidate_source
        and "候选不是买入指令" in candidate_source
        and "不调用 Tushare、DeepSeek 或 GitHub" in candidate_source
    )
    rows = [
        _candidate_browser_qa_runbook_row(
            "candidate_browser_qa_runbook_ready",
            "passed_static_policy" if runbook_ready else "blocked",
            passed=runbook_ready,
            evidence="scripts/candidate_radar_browser_qa_runbook.py pins route, viewports, criteria, artifact policy, and pending browser execution state",
        ),
        _candidate_browser_qa_runbook_row(
            "shared_motion_runner_covers_candidate_route",
            "passed_static_policy" if runner_available else "blocked",
            passed=runner_available,
            evidence="scripts/motion_browser_qa_runner.mjs includes #candidates, local-only URL policy, ignored artifact path, and no-provider/no-trade flags",
        ),
        _candidate_browser_qa_runbook_row(
            "candidate_route_source_ready",
            "passed_static_policy" if route_source_ready else "blocked",
            passed=route_source_ready,
            evidence="CandidateRadar.tsx exposes result cluster, clarity rail, delta rows, and button-gated local scan controls",
        ),
        _candidate_browser_qa_runbook_row(
            "default_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Default-motion browser pass is explicit and not run by GET cache or push-gate static checks.",
            required_before_completion=False,
        ),
        _candidate_browser_qa_runbook_row(
            "reduced_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Reduced-motion browser pass is explicit and not run by GET cache or push-gate static checks.",
            required_before_completion=False,
        ),
        _candidate_browser_qa_runbook_row(
            "candidate_radar_performance_trace_pending",
            "execution_pending",
            passed=False,
            evidence="Browser first-stable, long-task, layout-shift, and route-transition evidence remains an explicit run artifact.",
            required_before_completion=False,
        ),
    ]
    blockers = [row["phase"] for row in rows if row["status"] == "blocked"]
    matrix_rows = [
        {
            "route": "#candidates",
            "label": "Candidate Radar",
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": "candidate result cluster, local scan controls, result-delta visibility, and no-trade boundaries",
            "required_checks": [
                "candidate result cluster is visible and readable",
                "local scan buttons are visible and do not auto-run",
                "delta/freshness/provider/degraded gaps remain visible",
                "no clipped primary labels or state clarity rail text",
                "no long task above the local budget",
            ],
            "visual_qa_complete": False,
            "browser_performance_trace_done": False,
        }
        for viewport in viewports
    ]
    local_ready = not blockers
    contract = {
        "schema_version": "candidate_radar_browser_qa_runbook.v1",
        "status": "candidate_radar_browser_qa_runbook_ready_execution_pending" if local_ready else "candidate_radar_browser_qa_runbook_blocked",
        "scope": "local_candidate_radar_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "local_runbook_ready": local_ready,
        "runner_available": runner_available,
        "candidate_route_source_ready": route_source_ready,
        "shared_runner_script": "scripts/motion_browser_qa_runner.mjs",
        "candidate_route": "#candidates",
        "artifact_root": ".stock_ming_3/motion_qa",
        "route_count": 1,
        "viewport_count": len(viewports),
        "qa_matrix_count": len(matrix_rows),
        "performance_budgets": {
            "candidate_radar_first_stable_ms": 1200,
            "route_transition_observed_ms": 500,
            "largest_motion_layout_shift": 0.1,
            "long_task_over_50ms_count": 0,
        },
        "visual_acceptance_criteria": [
            "candidate result cluster remains readable without opening raw JSON",
            "quick/watchlist/custom/full-pool/deep-scan controls remain visibly button-gated",
            "result-delta and previous-cache rows do not imply a trade recommendation",
            "provider/freshness/degraded gaps remain visible and are not hidden by motion",
            "mobile layout does not clip primary labels, state clarity rails, or action buttons",
            "reduced-motion mode preserves readable state boundaries",
        ],
        "row_count": len(rows),
        "blocking_phase_count": len(blockers),
        "blockers": blockers,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "visual_qa_complete": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "Runbook availability prepares targeted Candidate Radar browser QA; it is not browser evidence, provider-backed parity, or production radar replacement.",
    }
    return contract, rows, matrix_rows


def _relative_project_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def _read_candidate_browser_qa_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_browser_qa_report_sort_key(path: Path, report: Mapping[str, Any]) -> tuple[float, str]:
    generated_at = str(report.get("generated_at") or "").strip()
    if generated_at:
        try:
            parsed = _dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            return parsed.timestamp(), str(path)
        except Exception:
            pass
    try:
        return path.stat().st_mtime, str(path)
    except Exception:
        return 0.0, str(path)


def _candidate_browser_qa_report_rows_passed(report: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        transition_observed = row.get("route_transition_observed_ms")
        transition_budget = row.get("route_transition_budget_ms") or _as_dict(report.get("performance_budgets")).get(
            "route_transition_observed_ms"
        )
        try:
            transition_within_budget = float(transition_observed) <= float(transition_budget)
        except Exception:
            transition_within_budget = False
        if (
            str(row.get("status") or "") != "passed"
            or row.get("visual_qa_complete") is not True
            or row.get("performance_trace_complete") is not True
            or int(row.get("long_task_over_50ms_count") or 0) != 0
            or int(row.get("clipped_count") or 0) != 0
            or not transition_within_budget
        ):
            return False
    return True


def _candidate_browser_qa_evidence_row(report: Mapping[str, Any], row: Mapping[str, Any], report_path: Path) -> dict[str, Any]:
    transition_observed = row.get("route_transition_observed_ms")
    transition_budget = row.get("route_transition_budget_ms") or _as_dict(report.get("performance_budgets")).get(
        "route_transition_observed_ms"
    )
    try:
        transition_within_budget = float(transition_observed) <= float(transition_budget)
    except Exception:
        transition_within_budget = False
    row_status = str(row.get("status") or "unknown")
    long_task_count = int(row.get("long_task_over_50ms_count") or 0)
    clipped_count = int(row.get("clipped_count") or 0)
    offscreen_count = int(row.get("offscreen_count") or 0)
    performance_trace_complete = row.get("performance_trace_complete") is True
    visual_complete = row.get("visual_qa_complete") is True and row_status == "passed"
    performance_passed = performance_trace_complete and transition_within_budget and long_task_count == 0
    return {
        "run_id": report.get("run_id") or report_path.parent.name,
        "generated_at": report.get("generated_at"),
        "reduced_motion": report.get("reduced_motion") is True,
        "route": str(row.get("route") or ""),
        "label": str(row.get("label") or "Candidate Radar"),
        "viewport": str(row.get("viewport") or ""),
        "width": row.get("width"),
        "height": row.get("height"),
        "status": row_status,
        "visual_qa_complete": visual_complete,
        "performance_trace_complete": performance_trace_complete,
        "performance_passed": performance_passed,
        "route_transition_observed_ms": transition_observed,
        "route_transition_budget_ms": transition_budget,
        "long_task_over_50ms_count": long_task_count,
        "largest_motion_layout_shift": row.get("largest_motion_layout_shift"),
        "clipped_count": clipped_count,
        "offscreen_count": offscreen_count,
        "review_required": row_status != "passed" or not visual_complete or not performance_passed,
        "artifact_report_path": _relative_project_path(report_path),
        "screenshot_path": _safe_text(row.get("screenshot_path"), limit=240),
        "reads_local_artifact_only": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_evidence_summary() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_paths = (
        sorted(MOTION_QA_ARTIFACT_ROOT.glob("*/motion_browser_qa_report.json"))
        if MOTION_QA_ARTIFACT_ROOT.exists()
        else []
    )
    report_entries: list[tuple[float, str, Path, dict[str, Any]]] = []
    for path in report_paths:
        report = _read_candidate_browser_qa_report(path)
        sort_ts, sort_path = _candidate_browser_qa_report_sort_key(path, report)
        report_entries.append((sort_ts, sort_path, path, report))
    report_entries.sort(key=lambda item: (item[0], item[1]))
    candidate_rows: list[dict[str, Any]] = []
    scanned_report_count = 0
    valid_report_count = 0
    candidate_report_count = 0
    passing_candidate_report_count = 0
    latest_report_path: str | None = None
    latest_run_id: str | None = None
    latest_generated_at: Any = None
    for _sort_ts, _sort_path, path, report in report_entries[-20:]:
        scanned_report_count += 1
        if not report:
            continue
        valid_report = (
            report.get("schema_version") == "command_center_3_motion_browser_qa_result.v1"
            and report.get("scope") == "explicit_local_browser_visual_performance_run"
            and report.get("local_urls_only") is True
            and report.get("starts_no_servers") is True
            and report.get("external_calls_triggered") is False
            and report.get("tushare_called") is False
            and report.get("deepseek_called") is False
            and report.get("github_called") is False
            and report.get("does_not_execute_trades") is True
            and report.get("does_not_modify_strategy_action") is True
        )
        if not valid_report:
            continue
        valid_report_count += 1
        report_candidate_rows = [
            row
            for row in _as_list(report.get("rows"))
            if isinstance(row, Mapping) and str(row.get("route") or "") == "#candidates"
        ]
        if not report_candidate_rows:
            continue
        candidate_report_count += 1
        if _candidate_browser_qa_report_rows_passed(report, report_candidate_rows):
            passing_candidate_report_count += 1
        latest_report_path = _relative_project_path(path)
        latest_run_id = str(report.get("run_id") or path.parent.name)
        latest_generated_at = report.get("generated_at")
        candidate_rows.extend(_candidate_browser_qa_evidence_row(report, row, path) for row in report_candidate_rows)

    candidate_rows = candidate_rows[-16:]
    row_count = len(candidate_rows)
    review_required_count = sum(1 for row in candidate_rows if row.get("review_required") is True)
    visual_passed_count = sum(1 for row in candidate_rows if row.get("visual_qa_complete") is True)
    performance_passed_count = sum(1 for row in candidate_rows if row.get("performance_passed") is True)
    required_viewports = {"desktop", "laptop", "tablet", "mobile"}
    default_motion_viewports = {
        str(row.get("viewport") or "")
        for row in candidate_rows
        if row.get("reduced_motion") is False and row.get("review_required") is False
    }
    reduced_motion_viewports = {
        str(row.get("viewport") or "")
        for row in candidate_rows
        if row.get("reduced_motion") is True and row.get("review_required") is False
    }
    default_motion_passed = required_viewports.issubset(default_motion_viewports)
    reduced_motion_passed = required_viewports.issubset(reduced_motion_viewports)
    missing_default_motion_viewports = sorted(required_viewports - default_motion_viewports)
    missing_reduced_motion_viewports = sorted(required_viewports - reduced_motion_viewports)
    motion_viewport_coverage_complete = default_motion_passed and reduced_motion_passed
    local_evidence_found = row_count > 0
    visual_passed = local_evidence_found and visual_passed_count == row_count and review_required_count == 0
    performance_passed = local_evidence_found and performance_passed_count == row_count and review_required_count == 0
    candidate_browser_qa_evidence_ready = visual_passed and performance_passed and motion_viewport_coverage_complete
    status = (
        "candidate_browser_qa_evidence_passed_local_artifact"
        if candidate_browser_qa_evidence_ready
        else "candidate_browser_qa_evidence_review_required_local_artifact"
        if local_evidence_found
        else "candidate_browser_qa_evidence_pending"
    )
    summary = {
        "schema_version": "candidate_radar_browser_qa_evidence.v1",
        "status": status,
        "scope": "local_candidate_radar_browser_qa_evidence_reader_no_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "artifact_root": ".stock_ming_3/motion_qa",
        "local_browser_qa_evidence_found": local_evidence_found,
        "scanned_report_count": scanned_report_count,
        "valid_report_count": valid_report_count,
        "candidate_report_count": candidate_report_count,
        "passing_candidate_report_count": passing_candidate_report_count,
        "report_count": candidate_report_count,
        "passing_report_count": passing_candidate_report_count,
        "candidate_route": "#candidates",
        "candidate_viewport_row_count": row_count,
        "review_required_count": review_required_count,
        "visual_passed_count": visual_passed_count,
        "performance_passed_count": performance_passed_count,
        "default_motion_passed": default_motion_passed,
        "reduced_motion_passed": reduced_motion_passed,
        "required_viewports": sorted(required_viewports),
        "default_motion_viewports": sorted(viewport for viewport in default_motion_viewports if viewport),
        "reduced_motion_viewports": sorted(viewport for viewport in reduced_motion_viewports if viewport),
        "default_motion_viewport_count": len(default_motion_viewports),
        "reduced_motion_viewport_count": len(reduced_motion_viewports),
        "missing_default_motion_viewports": missing_default_motion_viewports,
        "missing_reduced_motion_viewports": missing_reduced_motion_viewports,
        "motion_viewport_coverage_complete": motion_viewport_coverage_complete,
        "candidate_browser_qa_evidence_ready": candidate_browser_qa_evidence_ready,
        "candidate_visual_qa_evidence_passed": visual_passed,
        "candidate_browser_performance_evidence_passed": performance_passed,
        "visual_qa_complete": visual_passed,
        "browser_performance_trace_done": performance_passed,
        "browser_visual_delta_qa_done": visual_passed,
        "latest_report_path": latest_report_path,
        "latest_run_id": latest_run_id,
        "latest_generated_at": latest_generated_at,
        "row_count": row_count,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This reads ignored local motion browser QA reports for #candidates only. It does not open a browser, write artifacts, prove provider parity, or mark production radar replacement complete.",
    }
    return summary, candidate_rows


def _candidate_browser_qa_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    blocks_review: bool = False,
    blocks_production: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "blocks_review": bool(blocks_review and not passed),
        "blocks_production": bool(blocks_production),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_review_contract(
    evidence_summary: Mapping[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    viewport_names = {str(row.get("viewport") or "") for row in evidence_rows}
    required_viewports = {"desktop", "laptop", "tablet", "mobile"}
    evidence_found = evidence_summary.get("local_browser_qa_evidence_found") is True
    review_rows = [
        _candidate_browser_qa_review_row(
            "explicit_post_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            passed=explicit_review,
            evidence="POST /api/candidate-radar/browser-qa-review creates the review record; GET cache only previews local evidence.",
            blocks_review=True,
            blocks_production=True,
        ),
        _candidate_browser_qa_review_row(
            "candidate_route_evidence_available",
            "passed" if evidence_found else "pending_local_report",
            passed=evidence_found,
            evidence="candidate_browser_qa_evidence_summary found ignored local runner rows for #candidates.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "candidate_viewport_matrix_complete",
            "passed" if required_viewports.issubset(viewport_names) else "pending_viewports",
            passed=required_viewports.issubset(viewport_names),
            evidence="desktop/laptop/tablet/mobile candidate rows must all be present in local runner evidence.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "visual_evidence_passed",
            "passed" if evidence_summary.get("candidate_visual_qa_evidence_passed") is True else "pending_visual_review",
            passed=evidence_summary.get("candidate_visual_qa_evidence_passed") is True,
            evidence="All candidate route rows must report visual_qa_complete and zero review rows.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "performance_evidence_passed",
            "passed" if evidence_summary.get("candidate_browser_performance_evidence_passed") is True else "pending_performance_review",
            passed=evidence_summary.get("candidate_browser_performance_evidence_passed") is True,
            evidence="All candidate route rows must include performance traces within local budgets and no long tasks.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "default_and_reduced_motion_coverage",
            "passed"
            if evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True
            else "pending_reduced_or_default_motion",
            passed=evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True,
            evidence="Both default-motion and reduced-motion candidate route passes are required before motion evidence can be reviewed as complete.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "ignored_artifact_policy_preserved",
            "passed" if evidence_summary.get("reads_ignored_local_reports_only") is True else "blocked_artifact_policy",
            passed=evidence_summary.get("reads_ignored_local_reports_only") is True,
            evidence="Review reads only ignored local reports and does not commit screenshots, videos, or JSON artifacts.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "production_replacement_stays_blocked",
            "passed",
            passed=True,
            evidence="Browser QA review cannot override full-pool/deep-scan/provider-backed acceptance blockers.",
            blocks_review=False,
            blocks_production=True,
        ),
    ]
    blocking_review_rows = [row for row in review_rows if row.get("blocks_review") is True]
    local_review_ready = explicit_review and not blocking_review_rows
    status = "candidate_browser_qa_review_ready_local_artifact" if local_review_ready else "candidate_browser_qa_review_pending"
    return {
        "schema_version": "candidate_radar_browser_qa_review.v1",
        "status": status,
        "scope": "button_gated_local_candidate_browser_qa_review_no_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "explicit_review_task_done": bool(explicit_review),
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "local_browser_qa_review_ready": local_review_ready,
        "local_browser_qa_evidence_found": evidence_found,
        "candidate_route": "#candidates",
        "required_viewports": sorted(required_viewports),
        "observed_viewports": sorted(viewport for viewport in viewport_names if viewport),
        "review_required_count": evidence_summary.get("review_required_count", 0),
        "evidence_row_count": len(evidence_rows),
        "review_row_count": len(review_rows),
        "blocking_review_count": len(blocking_review_rows),
        "blocking_review_keys": [str(row.get("criterion")) for row in blocking_review_rows],
        "default_motion_passed": evidence_summary.get("default_motion_passed") is True,
        "reduced_motion_passed": evidence_summary.get("reduced_motion_passed") is True,
        "motion_viewport_coverage_complete": evidence_summary.get("motion_viewport_coverage_complete") is True,
        "default_motion_viewports": evidence_summary.get("default_motion_viewports", []),
        "reduced_motion_viewports": evidence_summary.get("reduced_motion_viewports", []),
        "missing_default_motion_viewports": evidence_summary.get("missing_default_motion_viewports", []),
        "missing_reduced_motion_viewports": evidence_summary.get("missing_reduced_motion_viewports", []),
        "candidate_visual_qa_evidence_passed": evidence_summary.get("candidate_visual_qa_evidence_passed") is True,
        "candidate_browser_performance_evidence_passed": evidence_summary.get(
            "candidate_browser_performance_evidence_passed"
        )
        is True,
        "rows": review_rows,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This review promotes local browser QA evidence only to a button-gated local review state. It does not execute browser QA, call providers, or complete production radar replacement.",
    }


def _candidate_browser_visual_performance_reviewed(packet: Mapping[str, Any]) -> bool:
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    return bool(
        browser_review.get("status") == "candidate_browser_qa_review_ready_local_artifact"
        and browser_review.get("explicit_review_task_done") is True
        and browser_review.get("local_browser_qa_review_ready") is True
        and browser_review.get("candidate_visual_qa_evidence_passed") is True
        and browser_review.get("candidate_browser_performance_evidence_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
        and browser_review.get("production_radar_replacement_complete") is False
        and browser_review.get("external_calls_triggered") is False
        and browser_review.get("tushare_called") is False
        and browser_review.get("deepseek_called") is False
        and browser_review.get("github_called") is False
        and browser_review.get("does_not_execute_trades") is True
        and browser_review.get("does_not_modify_strategy_action") is True
        and browser_review.get("candidate_is_not_buy_instruction") is True
    )


def _fast_scan_readiness_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    production_blocker: bool = False,
    user_visible: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": passed,
        "evidence": evidence,
        "production_blocker": production_blocker and not passed,
        "user_visible": user_visible,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _fast_scan_readiness_rows(
    *,
    mode: str,
    scan_mode: str,
    cache_source: str,
    coverage: Mapping[str, Any],
    scan_execution_summary: Mapping[str, Any],
    scan_acceptance_rows: list[dict[str, Any]],
    parity_inventory: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    runtime_budget_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    acceptance_by_key = {str(row.get("check_key")): row for row in scan_acceptance_rows}
    provider_gap_count = int(scan_execution_summary.get("provider_gap_count") or 0)
    degraded_count = int(scan_execution_summary.get("degraded_mode_active_count") or 0)
    freshness_state = str(scan_execution_summary.get("freshness_state") or "unknown")
    local_modes_ready = set(SUPPORTED_LOCAL_SCAN_MODES) >= {"quick_cache_scan", "watchlist_scan", "custom_pool_scan"}
    return [
        _fast_scan_readiness_row(
            "page_render_does_not_scan",
            "passed" if coverage_detail.get("does_not_scan_full_market_on_render") is True else "blocked",
            passed=coverage_detail.get("does_not_scan_full_market_on_render") is True,
            evidence="GET cache and React render display persisted/cache packet only.",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "cache_get_is_read_only",
            "passed",
            passed=True,
            evidence=f"mode={mode}; cache_source={cache_source}; scan_mode={scan_mode}",
        ),
        _fast_scan_readiness_row(
            "button_task_receipt_contract",
            "passed" if scan_execution_summary.get("writes_sqlite_packet") is not None else "blocked",
            passed=scan_execution_summary.get("writes_sqlite_packet") is not None,
            evidence="POST scan tasks return local task_id and write/read SQLite packet when executed.",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "local_scan_modes_supported",
            "passed" if local_modes_ready else "blocked",
            passed=local_modes_ready,
            evidence="/".join(sorted(SUPPORTED_LOCAL_SCAN_MODES)),
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "legacy_signal_groups_visible",
            "gap_reported" if int(coverage.get("missing_signal_group_count") or 0) else "passed",
            passed=True,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing={coverage.get('missing_signal_group_count')}",
        ),
        _fast_scan_readiness_row(
            "legacy_parity_gap_visible",
            "gap_reported" if int(parity_inventory.get("gap_or_future_count") or 0) else "passed",
            passed=True,
            evidence=f"mapped_or_partial={parity_inventory.get('mapped_or_partial_count')}; gap_or_future={parity_inventory.get('gap_or_future_count')}",
        ),
        _fast_scan_readiness_row(
            "provider_gap_visible",
            "gap_reported" if provider_gap_count else "passed",
            passed=True,
            evidence=f"provider_gap_count={provider_gap_count}; degraded_active={degraded_count}",
        ),
        _fast_scan_readiness_row(
            "freshness_research_only_boundary",
            str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "unknown"),
            passed=True,
            evidence=f"freshness={freshness_state}; stale/unknown inputs remain display-only.",
        ),
        _fast_scan_readiness_row(
            "last_success_cache_visible",
            "passed" if cache_source in {"sqlite_meta", "snapshot", "snapshot_cache", "local_builder"} or candidate_rows else "empty_reported",
            passed=True,
            evidence=f"cache_source={cache_source}; candidate_rows={len(candidate_rows)}; empty state does not trigger broad scan.",
        ),
        _fast_scan_readiness_row(
            "local_pool_skips_visible",
            "passed" if not local_pool_audit or local_pool_audit.get("skipped_candidate_count") is not None else "input_reported",
            passed=True,
            evidence=f"input={local_pool_audit.get('input_candidate_count')}; normalized={local_pool_audit.get('normalized_candidate_count')}",
        ),
        _fast_scan_readiness_row(
            "runtime_budget_contract_visible",
            "passed" if runtime_budget_contract.get("status") == "fast_scan_runtime_budget_ready" else "blocked",
            passed=runtime_budget_contract.get("status") == "fast_scan_runtime_budget_ready",
            evidence=f"display_limit={runtime_budget_contract.get('display_candidate_limit')}; worker_threshold={runtime_budget_contract.get('worker_required_universe_threshold')}",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "full_pool_boundary_plan_only",
            "plan_only" if full_pool_scan_plan.get("status") == "full_pool_plan_ready" else "not_executed",
            passed=True,
            evidence=f"full_pool_scan_done={bool(full_pool_scan_plan.get('full_pool_scan_done') is True)}; worker_required={full_pool_scan_plan.get('worker_task_required')}",
        ),
        _fast_scan_readiness_row(
            "deep_scan_boundary_plan_only",
            "plan_only" if deep_scan_plan.get("status") == "deep_scan_plan_ready" else "not_executed",
            passed=True,
            evidence=f"deep_scan_done={bool(deep_scan_plan.get('deep_scan_done') is True)}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
        ),
        _fast_scan_readiness_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            evidence="Candidate rows remain research-only and never mutate strategy action or holdings.",
        ),
        _fast_scan_readiness_row(
            "production_full_replacement_pending",
            "pending",
            passed=False,
            evidence="Real full-pool/deep-scan execution and provider-backed parity acceptance remain future work.",
            production_blocker=False,
        ),
    ]


def _fast_scan_readiness_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    pending = [row["criterion"] for row in rows if row.get("status") == "pending" and not row.get("production_blocker")]
    passed_count = sum(1 for row in rows if row.get("passed") is True)
    static_ready = not blockers
    return {
        "schema_version": "candidate_radar_fast_scan_readiness.v1",
        "status": "fast_scan_local_ready_full_pool_pending" if static_ready else "fast_scan_blocked",
        "scope": "local_cache_task_readiness_not_full_pool_or_provider_acceptance",
        "ltg": "LTG-13",
        "local_fast_scan_ready": static_ready,
        "production_radar_replacement_complete": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "row_count": len(rows),
        "passed_count": passed_count,
        "blocking_criterion_count": len(blockers),
        "soft_blocker_count": len(pending),
        "blockers": blockers,
        "soft_blockers": pending,
        "cache_only": True,
        "post_task_required_for_scan": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "next_action": "implement worker-backed full-pool/deep-scan execution and provider-backed parity acceptance before retiring legacy radar fallback.",
    }


def _no_feature_loss_acceptance_row(
    criterion: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    required_for_production_replacement: bool = True,
    gap_visible: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_ready": bool(production_ready),
        "required_for_production_replacement": bool(required_for_production_replacement),
        "blocks_production_replacement": bool(required_for_production_replacement and not production_ready),
        "gap_visible": bool(gap_visible),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _no_feature_loss_acceptance_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = _as_dict(packet.get("counts"))
    policy = _as_dict(packet.get("policy"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    readiness = _as_dict(packet.get("fast_scan_readiness_audit"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    output_total = int(parity.get("output_contract_field_count") or len(_as_list(packet.get("legacy_output_contract_rows"))))
    output_mapped = int(parity.get("output_contract_mapped_count") or counts.get("legacy_output_mapped_count") or 0)
    missing_signal_count = int(coverage.get("missing_signal_group_count") or 0)
    parity_gap_count = int(parity.get("gap_or_future_count") or counts.get("legacy_parity_gap_count") or 0)
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True)
    browser_visual_perf_reviewed = _candidate_browser_visual_performance_reviewed(packet)
    return [
        _no_feature_loss_acceptance_row(
            "page_render_zero_scan",
            "passed" if policy.get("does_not_scan_market") is True else "blocked",
            local_contract_passed=policy.get("does_not_scan_market") is True,
            production_ready=policy.get("does_not_scan_market") is True,
            evidence="React page render and GET cache display persisted/cache packet only.",
            next_action="Keep broad scans behind explicit POST task buttons.",
        ),
        _no_feature_loss_acceptance_row(
            "cache_get_external_boundary",
            "passed" if packet.get("external_calls_triggered") is False else "blocked",
            local_contract_passed=packet.get("external_calls_triggered") is False,
            production_ready=packet.get("external_calls_triggered") is False,
            evidence="GET candidate cache does not call Tushare, DeepSeek, GitHub, or trading interfaces.",
            next_action="Preserve cache-only reads and keep provider/model calls button gated.",
        ),
        _no_feature_loss_acceptance_row(
            "local_fast_scan_modes",
            "passed" if readiness.get("local_fast_scan_ready") is True else "blocked",
            local_contract_passed=readiness.get("local_fast_scan_ready") is True,
            production_ready=readiness.get("local_fast_scan_ready") is True,
            evidence=f"supported_local_scan_modes={packet.get('supported_local_scan_modes')}",
            next_action="Keep quick/watchlist/custom scan modes local and task based.",
        ),
        _no_feature_loss_acceptance_row(
            "legacy_signal_groups_visible",
            "gap_reported" if missing_signal_count else "passed",
            local_contract_passed=True,
            production_ready=missing_signal_count == 0,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing={missing_signal_count}",
            next_action="Map each missing legacy signal group or keep the gap visible before retiring fallback.",
            gap_visible=missing_signal_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "legacy_parity_rows_visible",
            "gap_reported" if parity_gap_count else "passed",
            local_contract_passed=True,
            production_ready=parity_gap_count == 0,
            evidence=f"mapped_or_partial={parity.get('mapped_or_partial_count')}; gap_or_future={parity_gap_count}",
            next_action="Close or explicitly accept legacy parity gaps before claiming production replacement.",
            gap_visible=parity_gap_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "legacy_output_contract_visible",
            "gap_reported" if output_total and output_mapped < output_total else "passed",
            local_contract_passed=True,
            production_ready=bool(output_total and output_mapped >= output_total),
            evidence=f"output_mapped={output_mapped}; output_total={output_total}",
            next_action="Keep absent output fields as missing_reported; do not invent legacy output values.",
            gap_visible=bool(output_total and output_mapped < output_total),
        ),
        _no_feature_loss_acceptance_row(
            "provider_signal_gaps_visible",
            "gap_reported" if provider_gap_count else "passed",
            local_contract_passed=True,
            production_ready=provider_gap_count == 0,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate missing provider signal groups through future explicit provider tasks.",
            gap_visible=provider_gap_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "freshness_research_only_boundary",
            "passed" if freshness_ready else "research_only_reported",
            local_contract_passed=True,
            production_ready=freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require current trade-calendar freshness before using candidates as current evidence.",
            gap_visible=not freshness_ready,
        ),
        _no_feature_loss_acceptance_row(
            "runtime_budget_contract_visible",
            "passed" if runtime_budget.get("status") == "fast_scan_runtime_budget_ready" else "blocked",
            local_contract_passed=runtime_budget.get("status") == "fast_scan_runtime_budget_ready",
            production_ready=runtime_budget.get("status") == "fast_scan_runtime_budget_ready",
            evidence=f"display_limit={runtime_budget.get('display_candidate_limit')}; worker_threshold={runtime_budget.get('worker_required_universe_threshold')}",
            next_action="Keep sync display capped and move large universes to worker execution.",
        ),
        _no_feature_loss_acceptance_row(
            "browser_performance_trace_pending",
            "reviewed_local_artifact" if browser_visual_perf_reviewed else "pending_visual_perf_trace",
            local_contract_passed=True,
            production_ready=browser_visual_perf_reviewed,
            evidence=(
                f"local_browser_qa_review_ready={browser_review.get('local_browser_qa_review_ready') is True}; "
                f"visual={browser_review.get('candidate_visual_qa_evidence_passed') is True}; "
                f"performance={browser_review.get('candidate_browser_performance_evidence_passed') is True}; "
                f"motion_viewport_coverage_complete={browser_review.get('motion_viewport_coverage_complete') is True}"
            ),
            next_action=(
                "Promote durable CI/browser evidence separately; local artifact review alone does not retire legacy radar."
                if browser_visual_perf_reviewed
                else "Run desktop/mobile browser trace validation before claiming the scan is stall-free in production."
            ),
        ),
        _no_feature_loss_acceptance_row(
            "full_pool_execution_pending",
            "completed" if full_pool_done else "pending_worker_execution",
            local_contract_passed=True,
            production_ready=full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}",
            next_action="Implement future worker-backed full-pool execution without page-load scanning.",
        ),
        _no_feature_loss_acceptance_row(
            "deep_scan_execution_pending",
            "completed" if deep_scan_done else "pending_worker_execution",
            local_contract_passed=True,
            production_ready=deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
            next_action="Implement future deep scan as a guarded task and keep DeepSeek manual/button gated.",
        ),
        _no_feature_loss_acceptance_row(
            "provider_backed_acceptance_pending",
            "pending_provider_acceptance",
            local_contract_passed=True,
            production_ready=False,
            evidence="No provider-backed radar parity acceptance is executed by cache reads or local plan tasks.",
            next_action="Run future provider-backed acceptance samples after Tushare interface validation is ready.",
        ),
        _no_feature_loss_acceptance_row(
            "trade_action_isolation",
            "passed" if packet.get("does_not_modify_strategy_action") is True else "blocked",
            local_contract_passed=packet.get("does_not_modify_strategy_action") is True,
            production_ready=packet.get("does_not_modify_strategy_action") is True,
            evidence="Radar candidates remain research-only and do not mutate strategy action, holdings, or orders.",
            next_action="Keep candidate selection separate from trading integration.",
        ),
    ]


def _attach_no_feature_loss_acceptance_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _no_feature_loss_acceptance_rows(view)
    local_blockers = [row["criterion"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["criterion"] for row in rows if row.get("blocks_production_replacement")]
    visible_gaps = [row["criterion"] for row in rows if row.get("gap_visible")]
    local_ready = not local_blockers
    contract = {
        "schema_version": "candidate_radar_no_feature_loss_acceptance.v1",
        "status": "no_feature_loss_acceptance_local_ready_production_pending" if local_ready else "no_feature_loss_acceptance_blocked",
        "scope": "local_fast_scan_no_feature_loss_contract_not_production_replacement",
        "ltg": "LTG-13",
        "local_no_feature_loss_contract_ready": local_ready,
        "production_radar_replacement_complete": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": _candidate_browser_visual_performance_reviewed(view),
        "browser_visual_delta_qa_done": _candidate_browser_visual_performance_reviewed(view),
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "visible_gap_count": len(visible_gaps),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "visible_gaps": visible_gaps,
        "cache_only": True,
        "post_task_required_for_scan": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This contract proves local no-feature-loss acceptance is visible and may include button-gated local browser QA artifact review. It does not prove production radar replacement, full-pool execution, deep-scan execution, provider-backed acceptance, or durable browser release evidence.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["no_feature_loss_acceptance_row_count"] = contract["row_count"]
    counts["no_feature_loss_local_blocker_count"] = contract["local_blocker_count"]
    counts["no_feature_loss_production_blocker_count"] = contract["production_blocker_count"]
    counts["no_feature_loss_visible_gap_count"] = contract["visible_gap_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["no_feature_loss_acceptance_contract_is_local"] = True
    policy["no_feature_loss_acceptance_is_not_production_replacement"] = True
    policy["legacy_fallback_required_until_full_pool_deep_scan_acceptance"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["no_feature_loss_acceptance_contract"] = contract
    view["no_feature_loss_acceptance_rows"] = rows
    view = _attach_replacement_gap_triage_contract(view)
    view = _attach_candidate_radar_promotion_blocker_audit(view)
    view = _attach_candidate_radar_production_activation_receipt(view)
    view = _attach_quant_projection_execution_request(view)
    view = _attach_provider_parity_execution_request(view)
    view = _attach_candidate_radar_worker_execution_recipe(view)
    view = _attach_candidate_radar_worker_execution_request(view)
    view = _attach_candidate_radar_full_pool_worker_fallback(view)
    view = _attach_candidate_radar_deep_scan_worker_fallback(view)
    view = _attach_candidate_radar_worker_runtime_linked_evidence(view)
    view = _attach_candidate_radar_next_execution_recipe(view)
    view = _attach_candidate_radar_durable_evidence_recipe(view)
    view = _attach_candidate_radar_production_stage_scope_manifest(view)
    view = _attach_candidate_radar_production_replacement_review(view)
    view = _attach_candidate_radar_production_promotion_dry_run(view)
    view = _attach_candidate_radar_legacy_retirement_review(view)
    view = _attach_candidate_radar_production_promotion_review(view)
    view = _attach_candidate_radar_production_stage_scope_manifest(view)
    return view


def _replacement_gap_triage_row(
    gap_key: str,
    category: str,
    severity: str,
    status: str,
    *,
    passed: bool,
    blocks_legacy_retirement: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "gap_key": gap_key,
        "category": category,
        "severity": severity,
        "status": status,
        "passed": bool(passed),
        "blocks_legacy_retirement": bool(blocks_legacy_retirement and not passed),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _replacement_gap_triage_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = _as_dict(packet.get("counts"))
    policy = _as_dict(packet.get("policy"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    output_total = int(parity.get("output_contract_field_count") or len(_as_list(packet.get("legacy_output_contract_rows"))))
    output_mapped = int(parity.get("output_contract_mapped_count") or counts.get("legacy_output_mapped_count") or 0)
    missing_signal_count = int(coverage.get("missing_signal_group_count") or 0)
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True)
    previous_diff_done = bool(result_delta.get("previous_cache_diff_done") is True)
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    browser_visual_perf_reviewed = _candidate_browser_visual_performance_reviewed(packet)
    browser_delta_done = bool(result_delta.get("browser_visual_delta_qa_done") is True or browser_visual_perf_reviewed)
    return [
        _replacement_gap_triage_row(
            "page_render_zero_scan_guardrail",
            "guardrail",
            "info",
            "passed" if policy.get("does_not_scan_market") is True else "blocked",
            passed=policy.get("does_not_scan_market") is True,
            blocks_legacy_retirement=True,
            evidence="GET cache and React render remain read-only and do not start a broad scan.",
            next_action="Keep all future radar scans behind explicit task buttons.",
        ),
        _replacement_gap_triage_row(
            "legacy_signal_group_mapping",
            "legacy_parity",
            "critical" if missing_signal_count else "ok",
            "gap_reported" if missing_signal_count else "passed",
            passed=missing_signal_count == 0,
            blocks_legacy_retirement=True,
            evidence=f"missing_signal_group_count={missing_signal_count}",
            next_action="Map missing legacy radar signal groups or keep Streamlit fallback available.",
        ),
        _replacement_gap_triage_row(
            "legacy_output_contract_mapping",
            "legacy_parity",
            "critical" if output_total and output_mapped < output_total else "ok",
            "gap_reported" if output_total and output_mapped < output_total else "passed",
            passed=bool(output_total and output_mapped >= output_total),
            blocks_legacy_retirement=True,
            evidence=f"output_mapped={output_mapped}; output_total={output_total}",
            next_action="Preserve every legacy output field or explicitly show it as missing before retirement.",
        ),
        _replacement_gap_triage_row(
            "provider_signal_coverage",
            "provider_acceptance",
            "critical" if provider_gap_count else "ok",
            "gap_reported" if provider_gap_count else "passed",
            passed=provider_gap_count == 0,
            blocks_legacy_retirement=True,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate provider-backed radar signals through future explicit provider tasks.",
        ),
        _replacement_gap_triage_row(
            "current_freshness_gate",
            "freshness",
            "critical" if not freshness_ready else "ok",
            "research_only_reported" if not freshness_ready else "passed",
            passed=freshness_ready,
            blocks_legacy_retirement=True,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require current trade-calendar freshness before treating candidates as current evidence.",
        ),
        _replacement_gap_triage_row(
            "previous_cache_delta_clarity",
            "result_delta",
            "pending" if not previous_diff_done else "ok",
            "pending_previous_cache_diff" if not previous_diff_done else "passed",
            passed=previous_diff_done,
            blocks_legacy_retirement=False,
            evidence=f"previous_cache_diff_done={previous_diff_done}; changed={result_delta.get('candidate_changed_count')}",
            next_action="Keep previous-cache diff visible when a persisted prior radar packet exists.",
        ),
        _replacement_gap_triage_row(
            "browser_visual_delta_qa",
            "visual_qa",
            "ok" if browser_delta_done else "blocking_pending",
            "pending_visual_qa" if not browser_delta_done else "passed",
            passed=browser_delta_done,
            blocks_legacy_retirement=True,
            evidence=(
                f"browser_visual_delta_qa_done={browser_delta_done}; "
                f"local_browser_qa_review_ready={browser_review.get('local_browser_qa_review_ready') is True}"
            ),
            next_action=(
                "Keep durable browser/CI promotion separate from legacy retirement."
                if browser_delta_done
                else "Run viewport visual QA so result changes are visible without overlap or occlusion."
            ),
        ),
        _replacement_gap_triage_row(
            "browser_performance_trace",
            "performance",
            "ok" if browser_visual_perf_reviewed else "blocking_pending",
            "passed" if browser_visual_perf_reviewed else "pending_perf_trace",
            passed=browser_visual_perf_reviewed,
            blocks_legacy_retirement=True,
            evidence=(
                f"local_browser_qa_review_ready={browser_review.get('local_browser_qa_review_ready') is True}; "
                f"visual={browser_review.get('candidate_visual_qa_evidence_passed') is True}; "
                f"performance={browser_review.get('candidate_browser_performance_evidence_passed') is True}"
            ),
            next_action=(
                "Keep provider/worker/durable-release blockers in place before legacy retirement."
                if browser_visual_perf_reviewed
                else "Run desktop/mobile trace validation before claiming the radar is stall-free in production."
            ),
        ),
        _replacement_gap_triage_row(
            "full_pool_worker_execution",
            "worker_pipeline",
            "blocking_pending" if not full_pool_done else "ok",
            "pending_worker_execution" if not full_pool_done else "passed",
            passed=full_pool_done,
            blocks_legacy_retirement=True,
            evidence=f"full_pool_scan_done={full_pool_done}",
            next_action="Implement worker-backed full-pool execution without page-load scanning.",
        ),
        _replacement_gap_triage_row(
            "deep_scan_execution",
            "worker_pipeline",
            "blocking_pending" if not deep_scan_done else "ok",
            "pending_worker_execution" if not deep_scan_done else "passed",
            passed=deep_scan_done,
            blocks_legacy_retirement=True,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
            next_action="Implement deep scan as a guarded task; keep DeepSeek manual/button gated.",
        ),
        _replacement_gap_triage_row(
            "provider_backed_acceptance",
            "provider_acceptance",
            "blocking_pending",
            "pending_provider_acceptance",
            passed=False,
            blocks_legacy_retirement=True,
            evidence=f"provider_backed_acceptance_done={bool(no_loss.get('provider_backed_acceptance_done') is True)}",
            next_action="Run provider-backed radar parity acceptance only after the Tushare task pipeline is ready.",
        ),
        _replacement_gap_triage_row(
            "trade_action_isolation",
            "safety",
            "ok",
            "passed" if packet.get("does_not_modify_strategy_action") is True and packet.get("does_not_execute_trades") is True else "blocked",
            passed=packet.get("does_not_modify_strategy_action") is True and packet.get("does_not_execute_trades") is True,
            blocks_legacy_retirement=True,
            evidence="Radar candidates remain research-only and do not mutate action, holdings, or orders.",
            next_action="Keep candidate radar isolated from trading integration.",
        ),
    ]


def _attach_replacement_gap_triage_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _replacement_gap_triage_rows(view)
    blocking_rows = [row for row in rows if row.get("blocks_legacy_retirement")]
    critical_rows = [row for row in rows if row.get("severity") == "critical"]
    pending_rows = [row for row in rows if "pending" in str(row.get("severity") or row.get("status") or "")]
    legacy_retirement_ready = not blocking_rows
    contract = {
        "schema_version": "candidate_radar_replacement_gap_triage.v1",
        "status": (
            "replacement_gap_triage_ready_for_legacy_retirement"
            if legacy_retirement_ready
            else "replacement_gap_triage_local_ready_legacy_retirement_blocked"
        ),
        "scope": "local_replacement_gap_triage_not_production_radar_replacement",
        "ltg": "LTG-13",
        "local_triage_ready": True,
        "legacy_retirement_ready": legacy_retirement_ready,
        "production_radar_replacement_complete": False,
        "legacy_fallback_required": not legacy_retirement_ready,
        "row_count": len(rows),
        "blocking_gap_count": len(blocking_rows),
        "critical_gap_count": len(critical_rows),
        "pending_gap_count": len(pending_rows),
        "blocking_gap_keys": [str(row.get("gap_key")) for row in blocking_rows],
        "critical_gap_keys": [str(row.get("gap_key")) for row in critical_rows],
        "high_priority_next_actions": [str(row.get("next_action")) for row in blocking_rows[:5]],
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This triage makes the blockers to retiring the legacy next-ticket radar visible. It is not full-pool execution, provider-backed acceptance, browser visual QA, or production replacement.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["replacement_gap_triage_row_count"] = contract["row_count"]
    counts["replacement_gap_triage_blocking_count"] = contract["blocking_gap_count"]
    counts["replacement_gap_triage_critical_count"] = contract["critical_gap_count"]
    counts["replacement_gap_triage_pending_count"] = contract["pending_gap_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["replacement_gap_triage_contract_is_local"] = True
    policy["replacement_gap_triage_is_not_production_replacement"] = True
    policy["legacy_radar_retirement_blocked_by_triage"] = not legacy_retirement_ready
    view["counts"] = counts
    view["policy"] = policy
    view["replacement_gap_triage_contract"] = contract
    view["replacement_gap_triage_rows"] = rows
    return view


def _promotion_blocker_row(
    criterion: str,
    category: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    next_action: str,
    blocks_promotion: bool = True,
    evidence_kind: str = "local_contract",
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "category": category,
        "status": status,
        "passed": bool(passed),
        "evidence_kind": evidence_kind,
        "evidence": evidence,
        "next_action": next_action,
        "blocks_promotion": bool(blocks_promotion and not passed),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_radar_promotion_blocker_audit(packet: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    counts = _as_dict(packet.get("counts"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    replacement = _as_dict(packet.get("replacement_gap_triage_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    browser_evidence = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    readiness = _as_dict(packet.get("fast_scan_readiness_audit"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    coverage = _as_dict(packet.get("coverage_detail_summary"))
    freshness = _as_dict(packet.get("freshness_state"))
    candidate_count = int(counts.get("candidate_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    provider_gap_count = int(coverage.get("provider_blocked_group_count") or 0) + int(
        coverage.get("stale_input_group_count") or 0
    ) + int(coverage.get("missing_provider_data_group_count") or 0)
    full_pool_done = full_pool_plan.get("full_pool_scan_done") is True
    deep_scan_done = deep_scan_plan.get("deep_scan_done") is True
    provider_acceptance_done = no_loss.get("provider_backed_acceptance_done") is True
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    browser_visual_passed = browser_evidence.get("candidate_visual_qa_evidence_passed") is True
    browser_perf_passed = browser_evidence.get("candidate_browser_performance_evidence_passed") is True
    rows = [
        _promotion_blocker_row(
            "local_fast_scan_ready",
            "local_readiness",
            "passed" if readiness.get("local_fast_scan_ready") is True else "blocked",
            passed=readiness.get("local_fast_scan_ready") is True,
            evidence=f"fast_scan_status={readiness.get('status')}; candidate_count={candidate_count}",
            next_action="Keep quick/watchlist/custom scan modes button-gated and cache-only.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "no_feature_loss_local_contract_ready",
            "feature_parity",
            "passed" if no_loss.get("local_no_feature_loss_contract_ready") is True else "blocked",
            passed=no_loss.get("local_no_feature_loss_contract_ready") is True,
            evidence=f"local_blockers={no_loss.get('local_blocker_count')}; production_blockers={no_loss.get('production_blocker_count')}",
            next_action="Keep no-feature-loss rows visible and close local blockers before production promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "legacy_retirement_triage_clear",
            "legacy_parity",
            "passed" if replacement.get("legacy_retirement_ready") is True else "blocked_legacy_retirement",
            passed=replacement.get("legacy_retirement_ready") is True,
            evidence=f"blocking_gap_count={replacement.get('blocking_gap_count')}; critical_gap_count={replacement.get('critical_gap_count')}",
            next_action="Resolve legacy signal/output/provider/browser/full/deep blockers before retiring old radar fallback.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "provider_signal_coverage_complete",
            "provider_acceptance",
            "passed" if provider_gap_count == 0 and provider_acceptance_done else "pending_provider_acceptance",
            passed=provider_gap_count == 0 and provider_acceptance_done,
            evidence=f"provider_gap_count={provider_gap_count}; provider_backed_acceptance_done={provider_acceptance_done}",
            next_action="Run explicit provider-backed radar parity samples after Tushare interface validation is ready.",
            blocks_promotion=True,
            evidence_kind="provider_acceptance_required",
        ),
        _promotion_blocker_row(
            "current_freshness_ready",
            "freshness",
            "passed" if freshness_ready else "research_only_freshness",
            passed=freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require trade-calendar current evidence before production radar promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "browser_visual_and_performance_reviewed",
            "browser_qa",
            "passed" if browser_review_ready and browser_visual_passed and browser_perf_passed else "pending_browser_qa_review",
            passed=browser_review_ready and browser_visual_passed and browser_perf_passed,
            evidence=f"review_ready={browser_review_ready}; visual={browser_visual_passed}; performance={browser_perf_passed}",
            next_action="Run and review ignored local browser QA evidence, then promote durable CI/browser evidence separately.",
            blocks_promotion=True,
            evidence_kind="browser_evidence_required",
        ),
        _promotion_blocker_row(
            "result_delta_clarity_complete",
            "result_delta",
            "passed" if result_delta.get("previous_cache_diff_done") is True else "pending_previous_cache_diff",
            passed=result_delta.get("previous_cache_diff_done") is True,
            evidence=f"previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}; visible_gap_count={result_delta.get('visible_gap_count')}",
            next_action="Keep added/removed/rank/score delta rows visible when a previous radar packet exists.",
            blocks_promotion=False,
        ),
        _promotion_blocker_row(
            "runtime_budget_ready_not_perf_trace",
            "performance",
            "pending_browser_performance_trace"
            if runtime_budget.get("browser_performance_trace_done") is not True
            else "passed",
            passed=runtime_budget.get("browser_performance_trace_done") is True,
            evidence=f"browser_performance_trace_done={runtime_budget.get('browser_performance_trace_done')}; large_universe_worker_required={runtime_budget.get('large_universe_worker_required')}",
            next_action="Use runtime budget as local guard only; browser trace remains required for production promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "full_pool_execution_complete",
            "worker_pipeline",
            "passed" if full_pool_done else "pending_worker_execution",
            passed=full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}; worker_task_required={full_pool_plan.get('worker_task_required')}",
            next_action="Implement worker-backed full-pool execution without page-render scanning.",
            blocks_promotion=True,
            evidence_kind="worker_execution_required",
        ),
        _promotion_blocker_row(
            "deep_scan_execution_complete",
            "worker_pipeline",
            "passed" if deep_scan_done else "pending_worker_execution",
            passed=deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={deep_scan_plan.get('deepseek_called') is True}",
            next_action="Implement guarded deep scan with explicit model/provider gates and no action mutation.",
            blocks_promotion=True,
            evidence_kind="worker_execution_required",
        ),
        _promotion_blocker_row(
            "trade_action_isolation_preserved",
            "safety",
            "passed" if packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True else "blocked",
            passed=packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True,
            evidence="Candidate Radar remains research-only and isolated from strategy action, holdings, orders, and broker paths.",
            next_action="Keep production radar promotion separate from any future trading integration.",
            blocks_promotion=True,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("blocks_promotion")]
    provider_rows = [
        row
        for row in rows
        if row.get("evidence_kind") == "provider_acceptance_required" and row.get("blocks_promotion") is True
    ]
    worker_rows = [
        row
        for row in rows
        if row.get("evidence_kind") == "worker_execution_required" and row.get("blocks_promotion") is True
    ]
    browser_rows = [
        row
        for row in rows
        if row.get("evidence_kind") == "browser_evidence_required" and row.get("blocks_promotion") is True
    ]
    promotion_ready = not blocking_rows
    contract = {
        "schema_version": "candidate_radar_promotion_blocker_audit.v1",
        "status": "candidate_radar_promotion_ready" if promotion_ready else "candidate_radar_promotion_blocked",
        "scope": "local_candidate_radar_promotion_audit_not_production_execution",
        "ltg": "LTG-13",
        "local_promotion_audit_ready": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "promotion_ready": promotion_ready,
        "row_count": len(rows),
        "blocking_promotion_count": len(blocking_rows),
        "provider_acceptance_blocker_count": len(provider_rows),
        "worker_execution_blocker_count": len(worker_rows),
        "browser_evidence_blocker_count": len(browser_rows),
        "blocking_promotion_keys": [str(row.get("criterion")) for row in blocking_rows],
        "high_priority_next_actions": [str(row.get("next_action")) for row in blocking_rows[:5]],
        "full_pool_scan_done": full_pool_done,
        "deep_scan_done": deep_scan_done,
        "provider_backed_acceptance_done": provider_acceptance_done,
        "browser_qa_review_ready": browser_review_ready,
        "browser_visual_evidence_passed": browser_visual_passed,
        "browser_performance_evidence_passed": browser_perf_passed,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This audit promotes no evidence by itself. It lists blockers that must be cleared before Candidate Radar can replace the legacy next-ticket radar without feature loss.",
    }
    return contract, rows


def _attach_candidate_radar_promotion_blocker_audit(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_promotion_blocker_audit(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_promotion_blocking_count"] = contract["blocking_promotion_count"]
    counts["candidate_radar_promotion_provider_blocker_count"] = contract["provider_acceptance_blocker_count"]
    counts["candidate_radar_promotion_worker_blocker_count"] = contract["worker_execution_blocker_count"]
    counts["candidate_radar_promotion_browser_blocker_count"] = contract["browser_evidence_blocker_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_promotion_audit_is_local"] = True
    policy["candidate_radar_promotion_audit_is_not_production_replacement"] = True
    policy["candidate_radar_promotion_requires_provider_worker_browser_evidence"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["candidate_radar_promotion_blocker_audit"] = contract
    view["candidate_radar_promotion_blocker_rows"] = rows
    return view


def _activation_receipt_row(
    activation_key: str,
    category: str,
    status: str,
    *,
    local_ready: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "activation_key": activation_key,
        "category": category,
        "status": status,
        "local_ready": bool(local_ready),
        "production_blocker": bool(production_blocker),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_radar_production_activation_receipt(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    quick_receipt = _as_dict(packet.get("quick_scan_execution_receipt"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    replacement = _as_dict(packet.get("replacement_gap_triage_contract"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))
    priority_explanation = _as_dict(packet.get("candidate_priority_explanation_contract"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    policy = _as_dict(packet.get("policy"))
    full_pool_done = full_pool_plan.get("full_pool_scan_done") is True
    deep_scan_done = deep_scan_plan.get("deep_scan_done") is True
    provider_acceptance_done = promotion.get("provider_backed_acceptance_done") is True
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    browser_visual_perf_reviewed = bool(
        browser_review_ready
        and browser_review.get("candidate_visual_qa_evidence_passed") is True
        and browser_review.get("candidate_browser_performance_evidence_passed") is True
    )
    trade_guard_ready = (
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("candidate_is_not_buy_instruction") is not False
    )
    rows = [
        _activation_receipt_row(
            "local_quick_scan_receipt_ready",
            "local_fast_path",
            "passed" if quick_receipt.get("local_quick_scan_receipt_ready") is True else "blocked",
            local_ready=quick_receipt.get("local_quick_scan_receipt_ready") is True,
            production_blocker=False,
            evidence=f"quick_status={quick_receipt.get('status')}; blockers={quick_receipt.get('local_blocker_count')}",
            next_action="Keep cache/quick/watchlist/custom scan receipt visible before comparing candidates.",
        ),
        _activation_receipt_row(
            "no_feature_loss_surface_ready",
            "feature_parity",
            "passed" if no_loss.get("local_no_feature_loss_contract_ready") is True else "blocked",
            local_ready=no_loss.get("local_no_feature_loss_contract_ready") is True,
            production_blocker=False,
            evidence=f"no_loss_status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            next_action="Keep legacy signal, output, provider, freshness, and runtime gaps visible.",
        ),
        _activation_receipt_row(
            "production_promotion_blocked_visible",
            "promotion_boundary",
            "passed" if promotion.get("local_promotion_audit_ready") is True else "blocked",
            local_ready=promotion.get("local_promotion_audit_ready") is True,
            production_blocker=promotion.get("promotion_ready") is not True,
            evidence=f"promotion_ready={promotion.get('promotion_ready')}; blockers={promotion.get('blocking_promotion_count')}",
            next_action="Use the blocker audit as the promotion checklist; do not treat it as promotion evidence.",
        ),
        _activation_receipt_row(
            "full_pool_worker_execution_required",
            "worker_pipeline",
            "completed" if full_pool_done else "pending_worker_execution",
            local_ready=True,
            production_blocker=not full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}; plan_status={full_pool_plan.get('status')}",
            next_action="Run future explicit worker-backed full-pool execution without page-render scanning.",
        ),
        _activation_receipt_row(
            "deep_scan_worker_execution_required",
            "worker_pipeline",
            "completed" if deep_scan_done else "pending_worker_execution",
            local_ready=True,
            production_blocker=not deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; plan_status={deep_scan_plan.get('status')}",
            next_action="Run future guarded deep scan as a task; keep model/provider calls explicitly gated.",
        ),
        _activation_receipt_row(
            "provider_backed_acceptance_required",
            "provider_acceptance",
            "completed" if provider_acceptance_done else "pending_provider_acceptance",
            local_ready=True,
            production_blocker=not provider_acceptance_done,
            evidence=f"provider_backed_acceptance_done={provider_acceptance_done}",
            next_action="Validate provider-backed radar parity only through explicit acceptance tasks.",
        ),
        _activation_receipt_row(
            "browser_visual_performance_review_required",
            "browser_qa",
            "reviewed_local_artifact" if browser_visual_perf_reviewed else "pending_browser_review",
            local_ready=True,
            production_blocker=not browser_visual_perf_reviewed,
            evidence=(
                f"local_browser_qa_review_ready={browser_review_ready}; "
                f"visual={browser_review.get('candidate_visual_qa_evidence_passed') is True}; "
                f"performance={browser_review.get('candidate_browser_performance_evidence_passed') is True}; "
                "durable_ci_evidence_complete=false"
            ),
            next_action="Keep the reviewed local browser artifact visible, then promote durable CI/browser evidence separately.",
        ),
        _activation_receipt_row(
            "legacy_retirement_stays_blocked",
            "legacy_retirement",
            "blocked" if replacement.get("legacy_retirement_ready") is not True else "ready_for_review",
            local_ready=True,
            production_blocker=replacement.get("legacy_retirement_ready") is not True,
            evidence=f"legacy_retirement_ready={replacement.get('legacy_retirement_ready')}; blocking_gaps={replacement.get('blocking_gap_count')}",
            next_action="Keep Streamlit fallback until full/deep/provider/browser evidence clears the retirement gate.",
        ),
        _activation_receipt_row(
            "priority_explanation_research_only",
            "research_boundary",
            "passed"
            if priority_explanation.get("priority_explanation_is_not_trade_signal") is True
            else "blocked",
            local_ready=priority_explanation.get("priority_explanation_is_not_trade_signal") is True,
            production_blocker=False,
            evidence=f"cached_rank_preserved={priority_explanation.get('cached_rank_preserved')}; rescore={priority_explanation.get('does_not_recompute_score') is not True}",
            next_action="Keep candidate priority explanations as cache-rank explanations, not trade signals.",
        ),
        _activation_receipt_row(
            "trade_action_isolation_preserved",
            "safety",
            "passed" if trade_guard_ready else "blocked",
            local_ready=trade_guard_ready,
            production_blocker=not trade_guard_ready,
            evidence="Candidate Radar remains isolated from action, holdings, orders, and broker paths.",
            next_action="Keep radar promotion separate from any future trading integration.",
        ),
        _activation_receipt_row(
            "no_external_calls_from_receipt",
            "safety",
            "passed"
            if policy.get("does_not_call_tushare") is True
            and policy.get("does_not_call_deepseek") is True
            and policy.get("does_not_call_github") is True
            else "blocked",
            local_ready=policy.get("does_not_call_tushare") is True
            and policy.get("does_not_call_deepseek") is True
            and policy.get("does_not_call_github") is True,
            production_blocker=False,
            evidence="Activation receipt is computed from the local packet and does not invoke providers, models, or remote services.",
            next_action="Preserve GET/cache/render no-provider boundaries and keep external-capable work POST gated.",
        ),
    ]
    local_blockers = [row["activation_key"] for row in rows if not row.get("local_ready")]
    production_blockers = [row["activation_key"] for row in rows if row.get("production_blocker")]
    missing_evidence_items = [
        key
        for key, done in {
            "full_pool_worker_execution_evidence": full_pool_done,
            "deep_scan_worker_execution_evidence": deep_scan_done,
            "provider_backed_parity_call_ledger": provider_acceptance_done,
            "browser_visual_performance_review": browser_visual_perf_reviewed,
            "durable_ci_or_packaged_runtime_evidence": False,
            "legacy_retirement_acceptance": replacement.get("legacy_retirement_ready") is True,
        }.items()
        if not done
    ]
    local_ready = not local_blockers
    contract = {
        "schema_version": "candidate_radar_production_activation_receipt.v1",
        "status": (
            "candidate_radar_activation_receipt_ready_production_blocked"
            if local_ready
            else "candidate_radar_activation_receipt_blocked"
        ),
        "scope": "local_candidate_radar_activation_receipt_no_execution_or_provider_call",
        "ltg": "LTG-13",
        "local_activation_receipt_ready": local_ready,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": full_pool_done,
        "deep_scan_done": deep_scan_done,
        "provider_backed_acceptance_done": provider_acceptance_done,
        "browser_visual_performance_reviewed": browser_visual_perf_reviewed,
        "durable_ci_evidence_complete": False,
        "candidate_is_not_buy_instruction": True,
        "allowed_next_step": "explicit_worker_full_pool_and_deep_scan_acceptance_then_provider_backed_parity_and_browser_review",
        "not_allowed_next_steps": [
            "treat quick scan as production radar replacement",
            "treat full_pool_plan as full_pool_scan_done",
            "treat deep_scan_plan as deep_scan_done",
            "treat local browser review as durable CI/release evidence",
            "call Tushare/DeepSeek/GitHub from GET cache or render",
            "treat candidates as buy instructions",
            "modify strategy action",
        ],
        "missing_evidence_items": missing_evidence_items,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "pending_evidence_count": len(missing_evidence_items),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This receipt only organizes the remaining activation evidence. It does not execute full-pool/deep-scan work, call providers/models, promote browser artifacts, retire legacy radar, or complete production replacement.",
    }
    return contract, rows


def _attach_candidate_radar_production_activation_receipt(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_production_activation_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_activation_receipt_ready"] = contract["local_activation_receipt_ready"]
    counts["candidate_radar_activation_blocker_count"] = contract["production_blocker_count"]
    counts["candidate_radar_activation_pending_evidence_count"] = contract["pending_evidence_count"]
    counts["candidate_radar_activation_row_count"] = contract["row_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_activation_receipt_is_local"] = True
    policy["candidate_radar_activation_receipt_is_not_production_replacement"] = True
    policy["candidate_radar_activation_requires_worker_provider_browser_evidence"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_activation_receipt",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=contract["status"],
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_production_activation_receipt"] = contract
    view["candidate_radar_production_activation_rows"] = rows
    return view


def _candidate_radar_worker_execution_recipe_row(
    recipe_key: str,
    category: str,
    status: str,
    *,
    local_ready: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "recipe_key": recipe_key,
        "category": category,
        "status": status,
        "local_ready": bool(local_ready),
        "production_blocker": bool(production_blocker),
        "recommended_order": recommended_order,
        "evidence": evidence,
        "next_action": next_action,
        "recipe_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_worker_execution_recipe(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_pipeline = _as_dict(packet.get("fast_scan_task_pipeline_contract"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    full_pool_receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan_receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    legacy_receipt = _as_dict(packet.get("legacy_parity_acceptance_receipt"))
    provider_parity_dry_run = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    activation = _as_dict(packet.get("candidate_radar_production_activation_receipt"))
    policy = _as_dict(packet.get("policy"))
    fast_path_ready = task_pipeline.get("local_task_pipeline_ready") is True
    no_loss_ready = no_loss.get("local_no_feature_loss_contract_ready") is True
    full_pool_local_ready = (
        full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
    )
    deep_scan_local_ready = (
        deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
    )
    legacy_ready = legacy_receipt.get("local_acceptance_receipt_ready") is True
    provider_ticket_visible = bool(provider_parity_dry_run.get("acceptance_scope_hash_short"))
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    activation_ready = activation.get("local_activation_receipt_ready") is True
    trade_guard_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("candidate_is_not_buy_instruction") is not False
    )
    rows = [
        _candidate_radar_worker_execution_recipe_row(
            "fast_scan_pipeline_locked",
            "fast_path",
            "passed_local_fast_path" if fast_path_ready else "blocked_fast_scan_pipeline",
            local_ready=fast_path_ready,
            production_blocker=False,
            evidence=f"pipeline_status={task_pipeline.get('status')}; local_task_pipeline_ready={fast_path_ready}",
            next_action="Keep quick/watchlist/custom scans cache-first while full/deep worker work stays separate.",
            recommended_order=1,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "no_feature_loss_surface_ready",
            "feature_parity",
            "passed_no_feature_loss_surface" if no_loss_ready else "blocked_no_feature_loss_surface",
            local_ready=no_loss_ready,
            production_blocker=False,
            evidence=f"no_loss_status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            next_action="Keep legacy signal groups, provider gaps, freshness gaps, and output fields visible.",
            recommended_order=2,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "full_pool_local_receipt_visible",
            "local_universe_receipt",
            "local_receipt_visible" if full_pool_local_ready else "pending_local_full_pool_receipt",
            local_ready=full_pool_local_ready,
            production_blocker=False,
            evidence=(
                f"local_full_pool_execution_done={full_pool_receipt.get('local_full_pool_execution_done')}; "
                f"worker_backed_execution_done={full_pool_receipt.get('worker_backed_execution_done')}"
            ),
            next_action="Use the local universe receipt as shape evidence only; do not treat it as worker execution.",
            recommended_order=3,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "deep_scan_local_review_visible",
            "local_deep_review",
            "local_review_visible" if deep_scan_local_ready else "pending_local_deep_scan_review",
            local_ready=deep_scan_local_ready,
            production_blocker=False,
            evidence=(
                f"local_deep_scan_review_done={deep_scan_receipt.get('local_deep_scan_review_done')}; "
                f"deep_scan_done={deep_scan_receipt.get('deep_scan_done')}"
            ),
            next_action="Use the local review receipt as no-feature-loss evidence only; do not treat it as deep scan.",
            recommended_order=4,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "worker_runtime_required",
            "worker_pipeline",
            "pending_worker_runtime",
            local_ready=activation_ready,
            production_blocker=True,
            evidence=(
                f"activation_status={activation.get('status')}; "
                f"allowed_next_step={activation.get('allowed_next_step')}"
            ),
            next_action="Implement explicit worker orchestration after worker production readiness is accepted.",
            recommended_order=5,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "full_pool_worker_task_scope_required",
            "worker_pipeline",
            "pending_worker_full_pool_scope",
            local_ready=True,
            production_blocker=True,
            evidence="Future full-pool worker task must consume bounded universe scope, storage datasets, task_id, and safe failure rows.",
            next_action="Bind full-pool execution to a future explicit worker task and call ledger.",
            recommended_order=6,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "deep_scan_worker_task_scope_required",
            "worker_pipeline",
            "pending_worker_deep_scan_scope",
            local_ready=True,
            production_blocker=True,
            evidence="Future deep-scan worker task must keep DeepSeek/model/provider work explicit, optional, and ledgered.",
            next_action="Bind deep-scan execution to a future explicit worker task with model/provider gates.",
            recommended_order=7,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "storage_dataset_contract_required",
            "storage",
            "pending_dataset_readiness",
            local_ready=True,
            production_blocker=True,
            evidence=f"required_storage_datasets={FULL_POOL_REQUIRED_STORAGE_DATASETS}",
            next_action="Prove daily/daily_basic/moneyflow/trade_cal datasets are current before worker production execution.",
            recommended_order=8,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "provider_parity_scope_ticket_required",
            "provider_parity",
            "scope_ticket_visible" if provider_ticket_visible else "pending_provider_parity_dry_run",
            local_ready=True,
            production_blocker=True,
            evidence=(
                f"provider_parity_status={provider_parity_dry_run.get('status')}; "
                f"scope_hash={provider_parity_dry_run.get('acceptance_scope_hash_short') or 'missing'}"
            ),
            next_action="Run provider parity dry-run, then bind the real provider/model task to that scope.",
            recommended_order=9,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "browser_visual_performance_promotion_required",
            "browser_qa",
            "local_review_ready" if browser_review_ready else "pending_browser_promotion",
            local_ready=True,
            production_blocker=True,
            evidence=f"local_browser_qa_review_ready={browser_review_ready}; durable_ci_evidence_complete=false",
            next_action="Promote only after default/reduced-motion visual and performance evidence is durable.",
            recommended_order=10,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "legacy_no_feature_loss_required",
            "legacy_retirement",
            "legacy_receipt_visible" if legacy_ready else "blocked_legacy_parity_receipt",
            local_ready=legacy_ready,
            production_blocker=True,
            evidence=(
                f"legacy_acceptance_status={legacy_receipt.get('status')}; "
                f"legacy_retirement_ready={legacy_receipt.get('legacy_retirement_ready')}"
            ),
            next_action="Keep Streamlit legacy radar fallback until worker/provider/browser evidence clears parity gates.",
            recommended_order=11,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "trade_action_isolation_preserved",
            "safety",
            "passed_research_only" if trade_guard_ready else "blocked_trade_action_boundary",
            local_ready=trade_guard_ready,
            production_blocker=not trade_guard_ready,
            evidence="Worker radar recipe cannot create orders, mutate holdings, or change strategy action.",
            next_action="Keep Candidate Radar output research-only and separate from any future trade chain.",
            recommended_order=12,
        ),
        _candidate_radar_worker_execution_recipe_row(
            "cache_render_boundary_preserved",
            "safety",
            "passed_no_worker_on_render"
            if policy.get("does_not_scan_market") is True and policy.get("post_task_required_for_scan") is True
            else "blocked_render_boundary",
            local_ready=policy.get("does_not_scan_market") is True and policy.get("post_task_required_for_scan") is True,
            production_blocker=False,
            evidence=(
                f"does_not_scan_market={policy.get('does_not_scan_market')}; "
                f"post_task_required_for_scan={policy.get('post_task_required_for_scan')}"
            ),
            next_action="Keep GET cache and React render silent; only explicit future worker tasks may scan.",
            recommended_order=13,
        ),
    ]
    local_blockers = [row["recipe_key"] for row in rows if not row.get("local_ready")]
    production_blockers = [row["recipe_key"] for row in rows if row.get("production_blocker")]
    local_ready = not local_blockers
    scope_input = {
        "schema_version": "candidate_radar_worker_execution_recipe.v1",
        "recommended_worker_full_pool_route": CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE,
        "recommended_worker_deep_scan_route": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE,
        "required_storage_datasets": list(FULL_POOL_REQUIRED_STORAGE_DATASETS),
        "required_legacy_signal_groups": [str(item.get("group")) for item in LEGACY_RADAR_SIGNAL_GROUPS],
        "recipe_keys": [str(row["recipe_key"]) for row in rows],
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
    }
    worker_scope_hash = hashlib.sha256(
        json.dumps(scope_input, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    contract = {
        "schema_version": "candidate_radar_worker_execution_recipe.v1",
        "status": (
            "candidate_radar_worker_execution_recipe_ready_production_pending"
            if local_ready
            else "candidate_radar_worker_execution_recipe_blocked_local_contract"
        ),
        "scope": "local_candidate_radar_worker_execution_recipe_no_worker_start",
        "ltg": "LTG-13",
        "worker_execution_scope_hash": worker_scope_hash,
        "worker_execution_scope_hash_short": worker_scope_hash[:16],
        "worker_execution_scope_hash_algorithm": "sha256",
        "worker_execution_scope_hash_input_includes_secret": False,
        "local_worker_execution_recipe_ready": local_ready,
        "ready_to_start_worker_from_cache": False,
        "requires_explicit_user_action": True,
        "recommended_worker_full_pool_task_type": CANDIDATE_FULL_POOL_WORKER_FALLBACK_TASK_TYPE,
        "recommended_worker_deep_scan_task_type": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_TASK_TYPE,
        "recommended_worker_full_pool_route": CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE,
        "recommended_worker_deep_scan_route": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE,
        "required_storage_datasets": list(FULL_POOL_REQUIRED_STORAGE_DATASETS),
        "required_legacy_signal_groups": [str(item.get("group")) for item in LEGACY_RADAR_SIGNAL_GROUPS],
        "required_legacy_parity_items": [str(item.get("key")) for item in LEGACY_RADAR_PARITY_ITEMS],
        "recommended_execution_order": [
            "render cached radar without starting worker",
            "run local quick/watchlist/custom scan first",
            "review local full-pool receipt and deep-scan local review",
            "confirm worker runtime readiness and storage dataset freshness",
            "execute future full-pool worker task with task_id and safe failure rows",
            "execute future deep-scan worker task with explicit provider/model gates",
            "run provider parity acceptance and browser promotion before legacy retirement",
        ],
        "not_allowed_next_steps": [
            "start worker from GET cache or React render",
            "treat worker recipe as worker execution done",
            "treat local full-pool receipt as worker-backed full-pool scan",
            "treat local deep-scan review as model/provider deep scan",
            "call Tushare/DeepSeek/GitHub from render",
            "skip provider/model call ledger",
            "turn candidates into buy instructions",
            "retire legacy radar before worker/provider/browser acceptance",
        ],
        "required_evidence_before_worker_promotion": [
            "worker runtime readiness receipt",
            "full-pool worker task_id and completion ledger",
            "deep-scan worker task_id and completion ledger",
            "storage dataset freshness and schema evidence",
            "provider-backed parity call ledger",
            "optional DeepSeek model ledger and sanitizer evidence",
            "browser visual/performance promotion evidence",
            "legacy radar retirement review",
        ],
        "worker_task_created": False,
        "worker_execution_implemented": False,
        "async_worker_execution_done": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "durable_ci_evidence_complete": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "page_render_starts_worker": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "rows": rows,
        "note": "This is a local worker execution recipe. It does not create worker tasks, start Celery/Redis, call providers/models, retire legacy radar, or complete production replacement.",
    }
    return contract, rows


def _attach_candidate_radar_worker_execution_recipe(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_worker_execution_recipe(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_worker_execution_recipe_row_count"] = contract["row_count"]
    counts["candidate_radar_worker_execution_recipe_local_blocker_count"] = contract["local_blocker_count"]
    counts["candidate_radar_worker_execution_recipe_production_blocker_count"] = contract["production_blocker_count"]
    counts["candidate_radar_worker_execution_recipe_ready"] = contract["local_worker_execution_recipe_ready"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_worker_execution_recipe_is_local"] = True
    policy["candidate_radar_worker_execution_recipe_does_not_start_worker"] = True
    policy["candidate_radar_worker_execution_recipe_requires_explicit_task"] = True
    policy["candidate_radar_worker_execution_recipe_is_not_production_replacement"] = True
    policy["candidate_radar_worker_execution_recipe_keeps_external_calls_false"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_worker_execution_recipe",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=contract["status"],
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_worker_execution_recipe"] = contract
    view["candidate_radar_worker_execution_rows"] = rows
    return view


def _candidate_worker_execution_request_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_WORKER_EXECUTION_REQUEST_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_worker_execution_request(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_request: bool = False,
    task_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = payload_safe or {}
    operator_approved = _coerce_bool(
        payload.get("operator_approved") or payload.get("user_approved") or payload.get("approved"),
        False,
    )
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    full_pool_receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan_receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    provider_parity = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    quant_dry_run = _as_dict(packet.get("search_quant_projection_acceptance_dry_run_receipt"))
    requested_scope_hash = _safe_text(
        payload.get("worker_execution_scope_hash") or payload.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(worker_recipe.get("worker_execution_scope_hash") or "", limit=128)
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    worker_recipe_ready = worker_recipe.get("local_worker_execution_recipe_ready") is True
    full_pool_local_visible = (
        full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
    )
    deep_scan_local_visible = (
        deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
    )
    provider_scope_visible = bool(provider_parity.get("acceptance_scope_hash"))
    quant_scope_visible = bool(quant_dry_run.get("acceptance_scope_hash"))
    rows = [
        _candidate_worker_execution_request_row(
            "explicit_post_worker_execution_request_done",
            "passed_explicit_post" if explicit_request else "blocked_missing_explicit_post",
            passed=explicit_request,
            local_blocker=not explicit_request,
            production_blocker=False,
            evidence=f"explicit_request={explicit_request}; task_id={task_id or ''}",
            next_action="Use only POST /api/candidate-radar/worker-execution-request to create the request ticket.",
        ),
        _candidate_worker_execution_request_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_request and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before a future worker-backed radar task.",
        ),
        _candidate_worker_execution_request_row(
            "worker_execution_recipe_ready",
            "passed_worker_recipe_ready" if worker_recipe_ready else "blocked_worker_recipe_not_ready",
            passed=worker_recipe_ready,
            local_blocker=not worker_recipe_ready,
            production_blocker=False,
            evidence=f"worker_recipe_status={worker_recipe.get('status')}; hash={worker_recipe.get('worker_execution_scope_hash_short') or 'missing'}",
            next_action="Keep the worker execution recipe visible before creating any worker task.",
        ),
        _candidate_worker_execution_request_row(
            "worker_execution_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            local_blocker=explicit_request and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind the request to the latest worker execution recipe hash.",
        ),
        _candidate_worker_execution_request_row(
            "local_full_pool_receipt_visible",
            "passed_local_full_pool_receipt" if full_pool_local_visible else "blocked_local_full_pool_receipt_missing",
            passed=full_pool_local_visible,
            local_blocker=not full_pool_local_visible,
            production_blocker=False,
            evidence=f"status={full_pool_receipt.get('status')}; local_done={full_pool_receipt.get('local_full_pool_execution_done')}",
            next_action="Run the local full-pool receipt path before future worker-backed full-pool execution.",
        ),
        _candidate_worker_execution_request_row(
            "local_deep_scan_review_visible",
            "passed_local_deep_scan_review" if deep_scan_local_visible else "blocked_local_deep_scan_review_missing",
            passed=deep_scan_local_visible,
            local_blocker=not deep_scan_local_visible,
            production_blocker=False,
            evidence=f"status={deep_scan_receipt.get('status')}; local_review_done={deep_scan_receipt.get('local_deep_scan_review_done')}",
            next_action="Run the local deep-scan review before future worker-backed deep scan.",
        ),
        _candidate_worker_execution_request_row(
            "provider_parity_scope_ticket_visible",
            "passed_provider_parity_scope" if provider_scope_visible else "blocked_provider_parity_scope_missing",
            passed=provider_scope_visible,
            local_blocker=not provider_scope_visible,
            production_blocker=False,
            evidence=f"status={provider_parity.get('status')}; hash={provider_parity.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Create the provider parity dry-run scope ticket before worker/provider promotion.",
        ),
        _candidate_worker_execution_request_row(
            "quant_projection_scope_ticket_visible",
            "scope_ticket_visible" if quant_scope_visible else "pending_optional_quant_projection_scope",
            passed=quant_scope_visible,
            local_blocker=False,
            production_blocker=not quant_scope_visible,
            evidence=f"status={quant_dry_run.get('status')}; hash={quant_dry_run.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Bind searched-symbol quant projection acceptance before claiming full radar replacement.",
        ),
        _candidate_worker_execution_request_row(
            "target_worker_routes_declared",
            "passed_target_routes_declared",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence=f"{CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE} and {CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE}",
            next_action="Implement future worker routes only after runtime worker readiness is accepted.",
        ),
        _candidate_worker_execution_request_row(
            "worker_execution_still_pending",
            "passed_request_only",
            passed=True,
            local_blocker=False,
            production_blocker=True,
            evidence="Request ticket does not create or execute any worker task.",
            next_action="Keep actual full-pool/deep-scan execution as a separate worker-backed task.",
        ),
        _candidate_worker_execution_request_row(
            "no_worker_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="No worker start, provider/model call, GitHub probe, trade, action mutation, or secret exposure.",
            next_action="Preserve this boundary while adding future worker execution evidence.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    if not explicit_request:
        status = "candidate_radar_worker_execution_request_missing"
        allowed_next_step = "create_button_gated_worker_execution_request"
    elif not operator_approved:
        status = "candidate_radar_worker_execution_request_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not worker_recipe_ready:
        status = "candidate_radar_worker_execution_request_blocked_worker_recipe_required"
        allowed_next_step = "restore_worker_execution_recipe"
    elif not requested_scope_hash:
        status = "candidate_radar_worker_execution_request_blocked_scope_hash_required"
        allowed_next_step = "bind_latest_worker_execution_scope_hash"
    elif not scope_hash_matches:
        status = "candidate_radar_worker_execution_request_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_worker_execution_scope_hash"
    elif not (full_pool_local_visible and deep_scan_local_visible):
        status = "candidate_radar_worker_execution_request_blocked_local_receipts_required"
        allowed_next_step = "run_local_full_pool_and_deep_scan_review_receipts"
    elif not provider_scope_visible:
        status = "candidate_radar_worker_execution_request_blocked_provider_parity_scope_required"
        allowed_next_step = "run_provider_parity_dry_run_scope_ticket"
    else:
        status = "candidate_radar_worker_execution_request_ready_manual_worker_task_pending"
        allowed_next_step = "manual_future_worker_task_implementation_after_runtime_readiness"
    local_ready = explicit_request and operator_approved and not local_blockers
    receipt = {
        "schema_version": CANDIDATE_WORKER_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_candidate_radar_worker_execution_request_no_worker_start",
        "mode": "button_gated_local_worker_execution_request",
        "ltg": "LTG-13",
        "route": CANDIDATE_WORKER_EXECUTION_REQUEST_ROUTE,
        "task_type": CANDIDATE_WORKER_EXECUTION_REQUEST_TASK_TYPE,
        "request_task_id": task_id or "",
        "explicit_worker_execution_request_done": explicit_request,
        "operator_approved": operator_approved,
        "local_execution_request_ready": local_ready,
        "ready_for_manual_worker_task_submission": local_ready,
        "worker_execution_recipe_ready": worker_recipe_ready,
        "worker_execution_scope_hash": expected_scope_hash,
        "worker_execution_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_worker_execution_scope_hash": requested_scope_hash,
        "requested_worker_execution_scope_hash_matches_latest": scope_hash_matches,
        "local_full_pool_receipt_visible": full_pool_local_visible,
        "local_deep_scan_review_visible": deep_scan_local_visible,
        "provider_parity_scope_ticket_visible": provider_scope_visible,
        "quant_projection_scope_ticket_visible": quant_scope_visible,
        "provider_parity_scope_hash": provider_parity.get("acceptance_scope_hash") or "",
        "provider_parity_scope_hash_short": provider_parity.get("acceptance_scope_hash_short") or "",
        "quant_projection_scope_hash": quant_dry_run.get("acceptance_scope_hash") or "",
        "quant_projection_scope_hash_short": quant_dry_run.get("acceptance_scope_hash_short") or "",
        "target_worker_full_pool_route": CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE,
        "target_worker_deep_scan_route": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE,
        "target_worker_full_pool_task_type": CANDIDATE_FULL_POOL_WORKER_FALLBACK_TASK_TYPE,
        "target_worker_deep_scan_task_type": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_TASK_TYPE,
        "allowed_next_step": allowed_next_step,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "blocking_criteria": local_blockers,
        "production_blockers": production_blockers,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_execution_implemented": False,
        "worker_started": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_task_dispatched": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "not_allowed_next_steps": [
            "create worker task from execution request",
            "start worker from execution request",
            "run full-pool scan from execution request",
            "run deep-scan from execution request",
            "call Tushare/DeepSeek/GitHub from execution request",
            "retire legacy radar fallback from execution request",
            "treat execution request as production radar replacement",
            "turn candidate rows into buy instructions",
        ],
        "row_count": len(rows),
        "rows": rows,
        "note": "This local request ticket binds Candidate Radar worker execution scope for a future task. It does not start workers, run full/deep scans, call providers/models, retire legacy fallback, or complete production replacement.",
    }
    return receipt, rows


def _attach_candidate_radar_worker_execution_request(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_worker_execution_request_receipt"))
    if existing.get("schema_version") == CANDIDATE_WORKER_EXECUTION_REQUEST_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [row for row in _as_list(view.get("candidate_radar_worker_execution_request_rows")) if isinstance(row, dict)]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_worker_execution_request(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_worker_execution_request_row_count"] = len(rows)
    counts["candidate_radar_worker_execution_request_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_worker_execution_request_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_worker_execution_request_ready"] = receipt.get("local_execution_request_ready") is True
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_worker_execution_request_is_button_gated"] = True
    policy["candidate_radar_worker_execution_request_is_local"] = True
    policy["candidate_radar_worker_execution_request_does_not_start_worker"] = True
    policy["candidate_radar_worker_execution_request_is_not_production_replacement"] = True
    policy["candidate_radar_worker_execution_request_keeps_external_calls_false"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_worker_execution_request",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_worker_execution_request_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_worker_execution_request_receipt"] = receipt
    view["candidate_radar_worker_execution_request_rows"] = rows
    return view


def _candidate_full_pool_worker_fallback_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "local_worker_fallback_task": True,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_full_pool_worker_fallback_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_execution: bool = False,
    task_id: str | None = None,
    executed_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = payload_safe or {}
    operator_approved = _coerce_bool(
        payload.get("operator_approved") or payload.get("user_approved") or payload.get("approved"),
        False,
    )
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    worker_request = _as_dict(packet.get("candidate_radar_worker_execution_request_receipt"))
    local_full_pool = _as_dict(packet.get("full_pool_local_execution_receipt"))
    candidate_rows = [row for row in _as_list(packet.get("candidate_rows")) if isinstance(row, dict)]
    requested_scope_hash = _safe_text(
        payload.get("worker_execution_scope_hash") or payload.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(
        worker_request.get("worker_execution_scope_hash")
        or worker_recipe.get("worker_execution_scope_hash")
        or "",
        limit=128,
    )
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    worker_request_ready = worker_request.get("local_execution_request_ready") is True
    local_full_pool_done = local_full_pool.get("local_full_pool_execution_done") is True
    candidate_rows_ready = bool(candidate_rows)
    rows = [
        _candidate_full_pool_worker_fallback_row(
            "explicit_post_full_pool_worker_fallback",
            "passed_explicit_post" if explicit_execution else "blocked_missing_explicit_post",
            passed=explicit_execution,
            local_blocker=not explicit_execution,
            production_blocker=False,
            evidence=f"route={CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE}; task_id={task_id or ''}",
            next_action="Use only the explicit POST route to run local worker-fallback full-pool evidence.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_execution and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before consuming a worker execution scope.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "worker_execution_request_ready",
            "passed_worker_request_ready" if worker_request_ready else "blocked_worker_request_required",
            passed=worker_request_ready,
            local_blocker=not worker_request_ready,
            production_blocker=False,
            evidence=f"status={worker_request.get('status')}; ready={worker_request_ready}",
            next_action="Create a scope-bound worker execution request before running the fallback route.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "worker_execution_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            local_blocker=explicit_execution and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind fallback execution to the latest approved worker execution request hash.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "local_full_pool_execution_consumed",
            "passed_local_full_pool_consumed" if local_full_pool_done else "blocked_local_full_pool_missing_or_empty",
            passed=local_full_pool_done,
            local_blocker=not local_full_pool_done,
            production_blocker=False,
            evidence=(
                f"status={local_full_pool.get('status')}; normalized={local_full_pool.get('normalized_candidate_count')}; "
                f"local_done={local_full_pool_done}"
            ),
            next_action="Keep fallback execution tied to a visible local full-pool receipt.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "candidate_rows_ready",
            "passed_candidate_rows_ready" if candidate_rows_ready else "blocked_empty_candidate_rows",
            passed=candidate_rows_ready,
            local_blocker=not candidate_rows_ready,
            production_blocker=False,
            evidence=f"candidate_row_count={len(candidate_rows)}",
            next_action="Provide local universe rows or cached candidates before running fallback execution.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "worker_runtime_still_pending",
            "pending_celery_redis_runtime",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="This route executes the local fallback path and does not start Celery or Redis.",
            next_action="Promote only after real worker process, queue, logs, cancellation, retry, and durable evidence exist.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "provider_backed_parity_still_pending",
            "pending_provider_backed_parity",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Fallback execution does not refresh provider rows or prove legacy signal parity.",
            next_action="Run provider-backed parity acceptance with safe call ledger before production replacement.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "browser_and_legacy_promotion_still_pending",
            "pending_browser_legacy_promotion",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Fallback execution does not promote browser performance evidence or retire legacy radar.",
            next_action="Keep browser promotion and legacy retirement review as separate acceptance steps.",
        ),
        _candidate_full_pool_worker_fallback_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="No provider/model/GitHub calls, no trades, no action mutation, and no secret persistence.",
            next_action="Preserve this boundary when replacing fallback with real worker execution.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    local_ready = explicit_execution and operator_approved and not local_blockers
    if not explicit_execution:
        status = "candidate_radar_full_pool_worker_fallback_missing"
        allowed_next_step = "run_button_gated_full_pool_worker_fallback"
    elif not operator_approved:
        status = "candidate_radar_full_pool_worker_fallback_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not worker_request_ready:
        status = "candidate_radar_full_pool_worker_fallback_blocked_worker_request_required"
        allowed_next_step = "create_worker_execution_request_ticket"
    elif not scope_hash_matches:
        status = "candidate_radar_full_pool_worker_fallback_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_worker_execution_scope_hash"
    elif not (local_full_pool_done and candidate_rows_ready):
        status = "candidate_radar_full_pool_worker_fallback_blocked_empty_local_universe"
        allowed_next_step = "provide_local_universe_or_cached_candidates"
    else:
        status = "candidate_radar_full_pool_worker_fallback_ready_worker_runtime_pending"
        allowed_next_step = "promote_to_real_worker_after_celery_redis_acceptance"
    receipt = {
        "schema_version": CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_full_pool_worker_fallback_no_worker_start",
        "ltg": "LTG-13/LTG-06",
        "route": CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE,
        "task_type": CANDIDATE_FULL_POOL_WORKER_FALLBACK_TASK_TYPE,
        "task_id": task_id or "",
        "executed_at": executed_at,
        "explicit_full_pool_worker_fallback_done": explicit_execution,
        "operator_approved": operator_approved,
        "local_worker_fallback_full_pool_done": local_ready,
        "local_worker_fallback_ready": local_ready,
        "ready_for_worker_runtime_promotion": False,
        "production_full_pool_scan_done": False,
        "full_pool_scan_done": False,
        "worker_backed_execution_done": False,
        "async_worker_execution_done": False,
        "worker_execution_implemented": False,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_broker_used": False,
        "provider_backed_acceptance_done": False,
        "model_execution_implemented": False,
        "browser_visual_performance_promoted": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "worker_execution_request_ready": worker_request_ready,
        "worker_execution_scope_hash": expected_scope_hash,
        "worker_execution_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_worker_execution_scope_hash": requested_scope_hash,
        "requested_worker_execution_scope_hash_matches_latest": scope_hash_matches,
        "local_full_pool_execution_done": local_full_pool_done,
        "input_candidate_count": local_full_pool.get("input_candidate_count") or 0,
        "normalized_candidate_count": local_full_pool.get("normalized_candidate_count") or 0,
        "candidate_row_count": len(candidate_rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "treat local worker fallback as Celery worker execution",
            "treat local worker fallback as provider-backed full-market acceptance",
            "start worker from GET cache or React render",
            "retire legacy radar fallback from local worker fallback",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "row_count": len(rows),
        "rows": rows,
        "note": "This receipt proves only a button-gated local worker-fallback full-pool route consumed local candidates. It is not Celery/Redis worker execution, provider-backed parity, or production radar replacement.",
    }
    return receipt, rows


def _attach_candidate_radar_full_pool_worker_fallback(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_full_pool_worker_fallback_receipt"))
    if existing.get("schema_version") == CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("candidate_radar_full_pool_worker_fallback_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_full_pool_worker_fallback_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_full_pool_worker_fallback_row_count"] = len(rows)
    counts["candidate_radar_full_pool_worker_fallback_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_full_pool_worker_fallback_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_full_pool_worker_fallback_ready"] = (
        receipt.get("local_worker_fallback_full_pool_done") is True
    )
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_full_pool_worker_fallback_is_button_gated"] = True
    policy["candidate_radar_full_pool_worker_fallback_is_local"] = True
    policy["candidate_radar_full_pool_worker_fallback_does_not_start_worker"] = True
    policy["candidate_radar_full_pool_worker_fallback_is_not_production_replacement"] = True
    policy["candidate_radar_full_pool_worker_fallback_keeps_external_calls_false"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_full_pool_worker_fallback_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_full_pool_worker_fallback_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_full_pool_worker_fallback_receipt"] = receipt
    view["candidate_radar_full_pool_worker_fallback_rows"] = rows
    return view


def _candidate_deep_scan_worker_fallback_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "local_worker_fallback_task": True,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_deep_scan_worker_fallback_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_execution: bool = False,
    task_id: str | None = None,
    executed_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = payload_safe or {}
    operator_approved = _coerce_bool(
        payload.get("operator_approved") or payload.get("user_approved") or payload.get("approved"),
        False,
    )
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    worker_request = _as_dict(packet.get("candidate_radar_worker_execution_request_receipt"))
    local_deep_review = _as_dict(packet.get("deep_scan_local_review_receipt"))
    candidate_rows = [row for row in _as_list(packet.get("candidate_rows")) if isinstance(row, dict)]
    requested_scope_hash = _safe_text(
        payload.get("worker_execution_scope_hash") or payload.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(
        worker_request.get("worker_execution_scope_hash")
        or worker_recipe.get("worker_execution_scope_hash")
        or "",
        limit=128,
    )
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    worker_request_ready = worker_request.get("local_execution_request_ready") is True
    local_deep_review_done = local_deep_review.get("local_deep_scan_review_done") is True
    candidate_rows_ready = bool(candidate_rows)
    rows = [
        _candidate_deep_scan_worker_fallback_row(
            "explicit_post_deep_scan_worker_fallback",
            "passed_explicit_post" if explicit_execution else "blocked_missing_explicit_post",
            passed=explicit_execution,
            local_blocker=not explicit_execution,
            production_blocker=False,
            evidence=f"route={CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE}; task_id={task_id or ''}",
            next_action="Use only the explicit POST route to consume local deep-scan fallback evidence.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_execution and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before consuming deep-scan worker scope.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "worker_execution_request_ready",
            "passed_worker_request_ready" if worker_request_ready else "blocked_worker_request_required",
            passed=worker_request_ready,
            local_blocker=not worker_request_ready,
            production_blocker=False,
            evidence=f"status={worker_request.get('status')}; ready={worker_request_ready}",
            next_action="Create a scope-bound worker execution request before running deep-scan fallback.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "worker_execution_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            local_blocker=explicit_execution and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind fallback execution to the latest approved worker execution request hash.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "local_deep_scan_review_consumed",
            "passed_local_deep_review_consumed" if local_deep_review_done else "blocked_local_deep_review_missing",
            passed=local_deep_review_done,
            local_blocker=not local_deep_review_done,
            production_blocker=False,
            evidence=f"status={local_deep_review.get('status')}; local_done={local_deep_review_done}",
            next_action="Run local deep-scan review before consuming the worker fallback route.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "candidate_rows_ready",
            "passed_candidate_rows_ready" if candidate_rows_ready else "blocked_empty_candidate_rows",
            passed=candidate_rows_ready,
            local_blocker=not candidate_rows_ready,
            production_blocker=False,
            evidence=f"candidate_row_count={len(candidate_rows)}",
            next_action="Provide local candidate rows before running deep-scan fallback execution.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "worker_runtime_still_pending",
            "pending_celery_redis_runtime",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="This route consumes local deep-scan fallback evidence and does not start Celery or Redis.",
            next_action="Promote only after real worker process, queue, logs, cancellation, retry, and durable evidence exist.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "deepseek_model_execution_still_pending",
            "pending_model_ledger",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Fallback execution does not call DeepSeek or produce a model ledger.",
            next_action="Keep model-backed deep research as a separate explicit task with sanitizer and ledger evidence.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "provider_backed_parity_still_pending",
            "pending_provider_backed_parity",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Fallback execution does not refresh provider rows or prove legacy signal parity.",
            next_action="Run provider-backed parity acceptance with safe call ledger before production replacement.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "browser_and_legacy_promotion_still_pending",
            "pending_browser_legacy_promotion",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Fallback execution does not promote browser performance evidence or retire legacy radar.",
            next_action="Keep browser promotion and legacy retirement review as separate acceptance steps.",
        ),
        _candidate_deep_scan_worker_fallback_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            passed=True,
            local_blocker=False,
            production_blocker=False,
            evidence="No provider/model/GitHub calls, no trades, no action mutation, and no secret persistence.",
            next_action="Preserve this boundary when replacing fallback with real worker/model execution.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    local_ready = explicit_execution and operator_approved and not local_blockers
    if not explicit_execution:
        status = "candidate_radar_deep_scan_worker_fallback_missing"
        allowed_next_step = "run_button_gated_deep_scan_worker_fallback"
    elif not operator_approved:
        status = "candidate_radar_deep_scan_worker_fallback_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not worker_request_ready:
        status = "candidate_radar_deep_scan_worker_fallback_blocked_worker_request_required"
        allowed_next_step = "create_worker_execution_request_ticket"
    elif not scope_hash_matches:
        status = "candidate_radar_deep_scan_worker_fallback_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_worker_execution_scope_hash"
    elif not (local_deep_review_done and candidate_rows_ready):
        status = "candidate_radar_deep_scan_worker_fallback_blocked_local_deep_review_required"
        allowed_next_step = "run_local_deep_scan_review_with_candidate_rows"
    else:
        status = "candidate_radar_deep_scan_worker_fallback_ready_worker_runtime_pending"
        allowed_next_step = "promote_to_real_worker_and_model_after_celery_redis_acceptance"
    receipt = {
        "schema_version": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_deep_scan_worker_fallback_no_worker_or_model_start",
        "ltg": "LTG-13/LTG-06/LTG-07",
        "route": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE,
        "task_type": CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_TASK_TYPE,
        "task_id": task_id or "",
        "executed_at": executed_at,
        "explicit_deep_scan_worker_fallback_done": explicit_execution,
        "operator_approved": operator_approved,
        "local_worker_fallback_deep_scan_done": local_ready,
        "local_worker_fallback_ready": local_ready,
        "ready_for_worker_runtime_promotion": False,
        "production_deep_scan_done": False,
        "deep_scan_done": False,
        "worker_deep_scan_execution_done": False,
        "worker_backed_execution_done": False,
        "async_worker_execution_done": False,
        "worker_execution_implemented": False,
        "worker_task_created": False,
        "worker_task_executed": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_broker_used": False,
        "provider_backed_acceptance_done": False,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "deepseek_model_ledger_complete": False,
        "browser_visual_performance_promoted": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "worker_execution_request_ready": worker_request_ready,
        "worker_execution_scope_hash": expected_scope_hash,
        "worker_execution_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_worker_execution_scope_hash": requested_scope_hash,
        "requested_worker_execution_scope_hash_matches_latest": scope_hash_matches,
        "local_deep_scan_review_done": local_deep_review_done,
        "candidate_row_count": len(candidate_rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "treat local deep-scan worker fallback as Celery worker execution",
            "treat local deep-scan worker fallback as DeepSeek/model deep research",
            "treat local deep-scan worker fallback as provider-backed parity",
            "start worker from GET cache or React render",
            "retire legacy radar fallback from local deep-scan fallback",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "row_count": len(rows),
        "rows": rows,
        "note": "This receipt proves only a button-gated local deep-scan worker-fallback route consumed local review evidence. It is not Celery/Redis worker execution, DeepSeek/model execution, provider-backed parity, or production radar replacement.",
    }
    return receipt, rows


def _attach_candidate_radar_deep_scan_worker_fallback(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_deep_scan_worker_fallback_receipt"))
    if existing.get("schema_version") == CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("candidate_radar_deep_scan_worker_fallback_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_deep_scan_worker_fallback_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_deep_scan_worker_fallback_row_count"] = len(rows)
    counts["candidate_radar_deep_scan_worker_fallback_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_deep_scan_worker_fallback_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_deep_scan_worker_fallback_ready"] = (
        receipt.get("local_worker_fallback_deep_scan_done") is True
    )
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_deep_scan_worker_fallback_is_button_gated"] = True
    policy["candidate_radar_deep_scan_worker_fallback_is_local"] = True
    policy["candidate_radar_deep_scan_worker_fallback_does_not_start_worker"] = True
    policy["candidate_radar_deep_scan_worker_fallback_does_not_call_deepseek"] = True
    policy["candidate_radar_deep_scan_worker_fallback_is_not_production_replacement"] = True
    policy["candidate_radar_deep_scan_worker_fallback_keeps_external_calls_false"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_deep_scan_worker_fallback_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_deep_scan_worker_fallback_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_deep_scan_worker_fallback_receipt"] = receipt
    view["candidate_radar_deep_scan_worker_fallback_rows"] = rows
    return view


def _read_candidate_worker_runtime_qa_execution_receipt() -> tuple[dict[str, Any], str]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(WORKER_RUNTIME_QA_EXECUTION_PACKET_KEY)
    except Exception:
        return {}, "packet_read_failed"
    if not isinstance(packet, dict):
        return {}, "packet_missing"
    receipt = _as_dict(packet.get("worker_runtime_qa_execution_receipt") or packet)
    if receipt.get("schema_version") != WORKER_RUNTIME_QA_EXECUTION_SCHEMA_VERSION:
        return {}, "schema_mismatch"
    return _json_safe(receipt), "packet_found"


def _candidate_worker_runtime_link_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_WORKER_RUNTIME_LINKED_EVIDENCE_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": False,
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "linked_from_ltg": "LTG-06",
        "linked_to_ltg": "LTG-13",
        "read_only_link": True,
        "worker_task_created": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_worker_complete": False,
        "production_radar_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_worker_runtime_linked_evidence() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt, read_status = _read_candidate_worker_runtime_qa_execution_receipt()
    receipt_visible = receipt.get("schema_version") == WORKER_RUNTIME_QA_EXECUTION_SCHEMA_VERSION
    linked = bool(
        receipt_visible
        and receipt.get("status") == "worker_runtime_qa_execution_ready_local_fallback_evidence"
        and receipt.get("local_runtime_qa_execution_done") is True
        and receipt.get("local_fallback_round_trip_verified") is True
        and receipt.get("task_log_round_trip_verified") is True
        and receipt.get("append_only_worker_log_verified") is True
        and receipt.get("cross_process_task_control_verified") is True
        and receipt.get("scheduler_default_off_runtime_verified") is True
        and receipt.get("provider_model_no_autoschedule_boundary_verified") is True
        and receipt.get("no_trade_no_action_boundary_verified") is True
        and receipt.get("production_worker_complete") is False
        and receipt.get("external_calls_triggered") is False
        and receipt.get("tushare_called") is False
        and receipt.get("deepseek_called") is False
        and receipt.get("github_called") is False
        and receipt.get("contains_secret") is False
    )
    rows = [
        _candidate_worker_runtime_link_row(
            "worker_runtime_qa_execution_packet_visible",
            "passed_worker_runtime_packet_visible" if receipt_visible else "pending_worker_runtime_packet",
            passed=receipt_visible,
            production_blocker=False,
            evidence=f"source_packet={WORKER_RUNTIME_QA_EXECUTION_PACKET_KEY}; read_status={read_status}; status={receipt.get('status') or 'missing'}",
            next_action="Run the explicit Worker Runtime QA execution task before relying on this local link.",
        ),
        _candidate_worker_runtime_link_row(
            "local_fallback_round_trip_verified",
            "passed_local_round_trip" if receipt.get("local_fallback_round_trip_verified") is True else "pending_local_round_trip",
            passed=receipt.get("local_fallback_round_trip_verified") is True,
            production_blocker=False,
            evidence=f"execution_task_id={receipt.get('execution_task_id') or ''}; local_runtime_done={receipt.get('local_runtime_qa_execution_done') is True}",
            next_action="Keep this as local fallback evidence only; live worker proof remains separate.",
        ),
        _candidate_worker_runtime_link_row(
            "task_log_append_only_and_control_verified",
            "passed_local_task_log_control"
            if (
                receipt.get("task_log_round_trip_verified") is True
                and receipt.get("append_only_worker_log_verified") is True
                and receipt.get("cross_process_task_control_verified") is True
            )
            else "pending_task_log_append_only_control",
            passed=bool(
                receipt.get("task_log_round_trip_verified") is True
                and receipt.get("append_only_worker_log_verified") is True
                and receipt.get("cross_process_task_control_verified") is True
            ),
            production_blocker=False,
            evidence=(
                f"task_log={receipt.get('task_log_round_trip_verified') is True}; "
                f"append_only={receipt.get('append_only_worker_log_verified') is True}; "
                f"cross_process={receipt.get('cross_process_task_control_verified') is True}"
            ),
            next_action="Use this as local task-store evidence, not Celery/Redis runtime evidence.",
        ),
        _candidate_worker_runtime_link_row(
            "scheduler_provider_model_boundary_verified",
            "passed_scheduler_provider_model_boundary"
            if (
                receipt.get("scheduler_default_off_runtime_verified") is True
                and receipt.get("provider_model_no_autoschedule_boundary_verified") is True
            )
            else "pending_scheduler_provider_model_boundary",
            passed=bool(
                receipt.get("scheduler_default_off_runtime_verified") is True
                and receipt.get("provider_model_no_autoschedule_boundary_verified") is True
            ),
            production_blocker=False,
            evidence=(
                f"scheduler_default_off={receipt.get('scheduler_default_off_runtime_verified') is True}; "
                f"provider_model_no_autoschedule={receipt.get('provider_model_no_autoschedule_boundary_verified') is True}"
            ),
            next_action="Keep radar worker execution/provider/model tasks button-gated and separate.",
        ),
        _candidate_worker_runtime_link_row(
            "celery_redis_live_worker_still_pending",
            "pending_live_celery_redis_worker",
            passed=False,
            production_blocker=True,
            evidence="The linked LTG-06 receipt is local runtime QA evidence; it does not start Celery or ping Redis.",
            next_action="Collect live Celery/Redis worker evidence in a separate approved worker-runtime cycle.",
        ),
        _candidate_worker_runtime_link_row(
            "radar_full_deep_provider_still_pending",
            "pending_radar_worker_provider_browser_evidence",
            passed=False,
            production_blocker=True,
            evidence="The link does not run Candidate Radar full-pool/deep-scan execution, provider parity, model ledger, or browser promotion.",
            next_action="Run explicit radar worker/provider/browser evidence tasks before any production replacement claim.",
        ),
        _candidate_worker_runtime_link_row(
            "no_external_trade_secret_boundary",
            "passed_no_external_trade_secret",
            passed=True,
            production_blocker=False,
            evidence="This read-only linkage calls no Tushare, DeepSeek, GitHub, worker process, browser, or trading path and stores no secrets.",
            next_action="Preserve this boundary when attaching future provider/model/worker evidence.",
        ),
    ]
    production_blockers = [str(row["criterion"]) for row in rows if row.get("production_blocker")]
    evidence = {
        "schema_version": CANDIDATE_WORKER_RUNTIME_LINKED_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "candidate_radar_worker_runtime_local_evidence_linked"
            if linked
            else "candidate_radar_worker_runtime_local_evidence_missing"
        ),
        "scope": "local_candidate_radar_worker_runtime_link_no_worker_or_provider_execution",
        "ltg": "LTG-13/LTG-06",
        "source_packet_key": WORKER_RUNTIME_QA_EXECUTION_PACKET_KEY,
        "source_packet_read_status": read_status,
        "source_worker_runtime_status": receipt.get("status") or "missing",
        "worker_runtime_evidence_visible": receipt_visible,
        "worker_runtime_local_evidence_linked": linked,
        "worker_runtime_direct_evidence_layer": "L3_local_worker_runtime_execution_evidence" if linked else "",
        "worker_runtime_execution_task_id": receipt.get("execution_task_id") or "",
        "worker_runtime_qa_scope_hash_short": receipt.get("runtime_qa_scope_hash_short") or "",
        "production_evidence_plan_scope_hash_short": receipt.get("production_evidence_plan_scope_hash_short") or "",
        "local_fallback_round_trip_verified": receipt.get("local_fallback_round_trip_verified") is True,
        "task_log_round_trip_verified": receipt.get("task_log_round_trip_verified") is True,
        "append_only_worker_log_verified": receipt.get("append_only_worker_log_verified") is True,
        "cross_process_task_control_verified": receipt.get("cross_process_task_control_verified") is True,
        "scheduler_default_off_runtime_verified": receipt.get("scheduler_default_off_runtime_verified") is True,
        "provider_model_no_autoschedule_boundary_verified": receipt.get(
            "provider_model_no_autoschedule_boundary_verified"
        )
        is True,
        "no_trade_no_action_boundary_verified": receipt.get("no_trade_no_action_boundary_verified") is True,
        "production_worker_complete": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_broker_used": False,
        "production_radar_replacement_complete": False,
        "worker_full_pool_execution_done": False,
        "worker_deep_scan_execution_done": False,
        "provider_backed_acceptance_done": False,
        "browser_visual_performance_promoted": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "local_blocker_count": 0,
        "production_blocker_count": len(production_blockers),
        "production_blockers": production_blockers,
        "allowed_next_step": "run_explicit_radar_worker_provider_browser_evidence_after_runtime_link_review",
        "not_allowed_next_steps": [
            "treat linked local runtime QA as Celery/Redis worker execution",
            "treat linked local runtime QA as radar full-pool or deep-scan execution",
            "treat linked local runtime QA as provider-backed parity",
            "call Tushare or DeepSeek from GET cache or React render",
            "retire legacy radar fallback from worker runtime linkage",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "row_count": len(rows),
        "rows": rows,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "note": "This link surfaces existing LTG-06 local runtime QA evidence for LTG-13 review. It is not live worker execution, provider parity, browser promotion, or production radar replacement.",
    }
    return evidence, rows


def _with_candidate_worker_runtime_link_row(
    receipt: Mapping[str, Any],
    rows: list[dict[str, Any]],
    evidence: Mapping[str, Any],
    *,
    row_factory: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    linked = evidence.get("worker_runtime_local_evidence_linked") is True
    link_row = row_factory(
        "worker_runtime_local_qa_execution_linked",
        "passed_local_runtime_qa_linked" if linked else "pending_local_runtime_qa_link",
        passed=linked,
        local_blocker=False,
        production_blocker=False,
        evidence=(
            f"linked={linked}; worker_runtime_status={evidence.get('source_worker_runtime_status')}; "
            f"task_id={evidence.get('worker_runtime_execution_task_id') or ''}"
        ),
        next_action="Use this as LTG-06 local runtime QA linkage only; real radar worker/provider/browser evidence remains separate.",
    )
    next_rows = [row for row in rows if row.get("criterion") != "worker_runtime_local_qa_execution_linked"]
    next_rows.append(link_row)
    next_receipt = dict(receipt)
    next_receipt["worker_runtime_local_evidence_linked"] = linked
    next_receipt["worker_runtime_direct_evidence_layer"] = evidence.get("worker_runtime_direct_evidence_layer") or ""
    next_receipt["worker_runtime_qa_execution_task_id"] = evidence.get("worker_runtime_execution_task_id") or ""
    next_receipt["worker_runtime_qa_source_status"] = evidence.get("source_worker_runtime_status") or "missing"
    next_receipt["worker_runtime_link_is_not_production_worker_completion"] = True
    next_receipt["row_count"] = len(next_rows)
    next_receipt["rows"] = next_rows
    return next_receipt, next_rows


def _attach_candidate_radar_worker_runtime_linked_evidence(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    evidence, rows = _candidate_radar_worker_runtime_linked_evidence()

    full_pool_receipt = _as_dict(view.get("candidate_radar_full_pool_worker_fallback_receipt"))
    if full_pool_receipt.get("schema_version") == CANDIDATE_FULL_POOL_WORKER_FALLBACK_SCHEMA_VERSION:
        full_pool_rows = [
            row
            for row in _as_list(view.get("candidate_radar_full_pool_worker_fallback_rows"))
            if isinstance(row, dict)
        ]
        full_pool_receipt, full_pool_rows = _with_candidate_worker_runtime_link_row(
            full_pool_receipt,
            full_pool_rows,
            evidence,
            row_factory=_candidate_full_pool_worker_fallback_row,
        )
        view["candidate_radar_full_pool_worker_fallback_receipt"] = full_pool_receipt
        view["candidate_radar_full_pool_worker_fallback_rows"] = full_pool_rows

    deep_scan_receipt = _as_dict(view.get("candidate_radar_deep_scan_worker_fallback_receipt"))
    if deep_scan_receipt.get("schema_version") == CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_SCHEMA_VERSION:
        deep_scan_rows = [
            row
            for row in _as_list(view.get("candidate_radar_deep_scan_worker_fallback_rows"))
            if isinstance(row, dict)
        ]
        deep_scan_receipt, deep_scan_rows = _with_candidate_worker_runtime_link_row(
            deep_scan_receipt,
            deep_scan_rows,
            evidence,
            row_factory=_candidate_deep_scan_worker_fallback_row,
        )
        view["candidate_radar_deep_scan_worker_fallback_receipt"] = deep_scan_receipt
        view["candidate_radar_deep_scan_worker_fallback_rows"] = deep_scan_rows

    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_worker_runtime_link_row_count"] = len(rows)
    counts["candidate_radar_worker_runtime_local_evidence_linked"] = (
        evidence.get("worker_runtime_local_evidence_linked") is True
    )
    counts["candidate_radar_worker_runtime_link_production_blocker_count"] = evidence.get(
        "production_blocker_count", 0
    )
    if full_pool_receipt:
        counts["candidate_radar_full_pool_worker_fallback_row_count"] = len(
            _as_list(view.get("candidate_radar_full_pool_worker_fallback_rows"))
        )
    if deep_scan_receipt:
        counts["candidate_radar_deep_scan_worker_fallback_row_count"] = len(
            _as_list(view.get("candidate_radar_deep_scan_worker_fallback_rows"))
        )

    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_worker_runtime_link_is_read_only"] = True
    policy["candidate_radar_worker_runtime_link_does_not_start_worker"] = True
    policy["candidate_radar_worker_runtime_link_calls_provider_or_model"] = False
    policy["candidate_radar_worker_runtime_link_is_not_production_worker_completion"] = True
    policy["candidate_radar_worker_runtime_link_is_not_production_radar_replacement"] = True

    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_worker_runtime_linked_evidence",
            source_snapshot=WORKER_RUNTIME_QA_EXECUTION_PACKET_KEY,
            row_count=len(rows),
            call_status=str(evidence.get("status") or "candidate_radar_worker_runtime_local_evidence_missing"),
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_worker_runtime_linked_evidence"] = evidence
    view["candidate_radar_worker_runtime_link_rows"] = rows
    return view


def _candidate_radar_next_execution_recipe_row(
    phase: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    required_before_fast_scan: bool = True,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "required_before_fast_scan": bool(required_before_fast_scan),
        "recommended_order": recommended_order,
        "evidence": evidence,
        "recipe_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_next_execution_recipe(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_pipeline = _as_dict(packet.get("fast_scan_task_pipeline_contract"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    full_pool_receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan_receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    provider_parity_dry_run = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    quant_dry_run = _as_dict(packet.get("search_quant_projection_acceptance_dry_run_receipt"))
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))
    activation = _as_dict(packet.get("candidate_radar_production_activation_receipt"))
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    worker_request = _as_dict(packet.get("candidate_radar_worker_execution_request_receipt"))
    policy = _as_dict(packet.get("policy"))
    counts = _as_dict(packet.get("counts"))
    candidate_count = int(counts.get("candidate_count") or 0)
    local_pipeline_ready = bool(task_pipeline.get("local_task_pipeline_ready"))
    no_loss_ready = bool(no_loss.get("local_no_feature_loss_contract_ready"))
    runtime_ready = runtime_budget.get("status") == "fast_scan_runtime_budget_ready"
    trade_guard_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("candidate_is_not_buy_instruction") is not False
    )
    cache_render_safe = bool(
        policy.get("does_not_scan_market") is True
        and policy.get("post_task_required_for_scan") is True
        and policy.get("does_not_call_tushare") is True
        and policy.get("does_not_call_deepseek") is True
        and policy.get("does_not_call_github") is True
    )
    provider_parity_ticket_visible = bool(provider_parity_dry_run.get("acceptance_scope_hash_short"))
    quant_ticket_visible = bool(quant_dry_run.get("acceptance_scope_hash_short"))
    quant_request_ready = quant_request.get("local_execution_request_ready") is True
    browser_review_ready = bool(browser_review.get("local_browser_qa_review_ready"))
    worker_recipe_ready = worker_recipe.get("local_worker_execution_recipe_ready") is True
    worker_request_ready = worker_request.get("local_execution_request_ready") is True
    rows = [
        _candidate_radar_next_execution_recipe_row(
            "cache_render_boundary",
            "passed_no_scan_on_render" if cache_render_safe else "blocked_render_boundary",
            cache_render_safe,
            evidence=(
                f"does_not_scan_market={policy.get('does_not_scan_market')}; "
                f"post_task_required_for_scan={policy.get('post_task_required_for_scan')}"
            ),
            recommended_order=1,
        ),
        _candidate_radar_next_execution_recipe_row(
            "fast_scan_task_pipeline_ready",
            "passed_local_task_pipeline" if local_pipeline_ready else "blocked_task_pipeline",
            local_pipeline_ready,
            evidence=f"pipeline_status={task_pipeline.get('status')}; candidate_count={candidate_count}",
            recommended_order=2,
        ),
        _candidate_radar_next_execution_recipe_row(
            "no_feature_loss_surface_ready",
            "passed_no_feature_loss_surface" if no_loss_ready else "blocked_no_feature_loss_surface",
            no_loss_ready,
            evidence=f"no_loss_status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            recommended_order=3,
        ),
        _candidate_radar_next_execution_recipe_row(
            "fast_scan_runtime_budget_visible",
            "passed_runtime_budget_visible" if runtime_ready else "blocked_runtime_budget",
            runtime_ready,
            evidence=(
                f"display_limit={runtime_budget.get('display_candidate_limit')}; "
                f"truncated={runtime_budget.get('candidate_display_truncated_count')}"
            ),
            recommended_order=4,
        ),
        _candidate_radar_next_execution_recipe_row(
            "trade_action_isolation_preserved",
            "passed_research_only" if trade_guard_ready else "blocked_trade_action_boundary",
            trade_guard_ready,
            evidence="Candidate Radar remains research-only: no orders, no holdings mutation, no strategy action mutation.",
            recommended_order=5,
        ),
        _candidate_radar_next_execution_recipe_row(
            "result_delta_clarity_visible",
            "passed_delta_surface_visible"
            if result_delta.get("local_result_delta_clarity_ready") is True
            else "pending_delta_surface",
            result_delta.get("local_result_delta_clarity_ready") is True,
            evidence=f"previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}; visible_gap_count={result_delta.get('visible_gap_count')}",
            required_before_fast_scan=False,
            recommended_order=6,
        ),
        _candidate_radar_next_execution_recipe_row(
            "local_full_pool_receipt_available",
            "local_receipt_visible"
            if full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
            else "pending_local_full_pool_receipt",
            full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1",
            evidence=(
                f"local_full_pool_execution_done={full_pool_receipt.get('local_full_pool_execution_done')}; "
                f"production_full_pool_scan_done={full_pool_receipt.get('production_full_pool_scan_done')}"
            ),
            required_before_fast_scan=False,
            recommended_order=7,
        ),
        _candidate_radar_next_execution_recipe_row(
            "local_deep_scan_review_available",
            "local_review_visible"
            if deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
            else "pending_local_deep_review",
            deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1",
            evidence=(
                f"local_deep_scan_review_done={deep_scan_receipt.get('local_deep_scan_review_done')}; "
                f"deep_scan_done={deep_scan_receipt.get('deep_scan_done')}"
            ),
            required_before_fast_scan=False,
            recommended_order=8,
        ),
        _candidate_radar_next_execution_recipe_row(
            "provider_parity_scope_ticket_required",
            "scope_ticket_visible" if provider_parity_ticket_visible else "pending_provider_parity_dry_run",
            provider_parity_ticket_visible,
            evidence=(
                f"status={provider_parity_dry_run.get('status')}; "
                f"scope_hash={provider_parity_dry_run.get('acceptance_scope_hash_short') or 'missing'}"
            ),
            required_before_fast_scan=False,
            recommended_order=9,
        ),
        _candidate_radar_next_execution_recipe_row(
            "quant_projection_scope_ticket_required",
            "scope_ticket_visible" if quant_ticket_visible else "pending_quant_projection_dry_run",
            quant_ticket_visible,
            evidence=(
                f"status={quant_dry_run.get('status')}; "
                f"scope_hash={quant_dry_run.get('acceptance_scope_hash_short') or 'missing'}"
            ),
            required_before_fast_scan=False,
            recommended_order=10,
        ),
        _candidate_radar_next_execution_recipe_row(
            "quant_projection_execution_request_visible",
            "execution_request_visible" if quant_request_ready else "pending_quant_projection_execution_request",
            quant_request_ready,
            evidence=(
                f"status={quant_request.get('status')}; "
                f"scope_hash_match={quant_request.get('requested_acceptance_scope_hash_matches_latest')}"
            ),
            required_before_fast_scan=False,
            recommended_order=11,
        ),
        _candidate_radar_next_execution_recipe_row(
            "worker_execution_recipe_visible",
            "worker_recipe_visible" if worker_recipe_ready else "pending_worker_execution_recipe",
            worker_recipe_ready,
            evidence=(
                f"worker_recipe_status={worker_recipe.get('status')}; "
                f"production_blockers={worker_recipe.get('production_blocker_count')}"
            ),
            required_before_fast_scan=False,
            recommended_order=12,
        ),
        _candidate_radar_next_execution_recipe_row(
            "worker_execution_request_visible",
            "worker_request_visible" if worker_request_ready else "pending_worker_execution_request",
            worker_request_ready,
            evidence=(
                f"worker_request_status={worker_request.get('status')}; "
                f"scope_hash_match={worker_request.get('requested_worker_execution_scope_hash_matches_latest')}"
            ),
            required_before_fast_scan=False,
            recommended_order=13,
        ),
        _candidate_radar_next_execution_recipe_row(
            "browser_qa_review_required",
            "local_review_ready" if browser_review_ready else "pending_browser_qa_review",
            browser_review_ready,
            evidence=f"browser_review_status={browser_review.get('status')}; ready={browser_review_ready}",
            required_before_fast_scan=False,
            recommended_order=14,
        ),
        _candidate_radar_next_execution_recipe_row(
            "production_promotion_boundary",
            "promotion_blocked_visible",
            promotion.get("promotion_ready") is not True and activation.get("production_radar_replacement_complete") is not True,
            evidence=(
                f"promotion_ready={promotion.get('promotion_ready')}; "
                f"activation_status={activation.get('status')}"
            ),
            required_before_fast_scan=False,
            recommended_order=15,
        ),
    ]
    blocking_rows = [row for row in rows if row["required_before_fast_scan"] and not row["passed"]]
    ready_for_user_fast_scan = not blocking_rows
    production_pending_phases = [
        row["phase"]
        for row in rows
        if not row["required_before_fast_scan"] and not row["passed"]
    ]
    contract = {
        "schema_version": "candidate_radar_next_execution_recipe.v1",
        "status": "candidate_radar_next_execution_ready_for_fast_scan"
        if ready_for_user_fast_scan
        else "candidate_radar_next_execution_blocked_local_fast_scan_readiness",
        "scope": "local_candidate_radar_next_execution_recipe_no_execution",
        "ltg": "LTG-13",
        "recipe_ready_for_user_fast_scan": ready_for_user_fast_scan,
        "ready_to_execute_from_cache": False,
        "requires_explicit_user_action": True,
        "recommended_fast_scan_route": "POST /api/candidate-radar/scan-quick",
        "recommended_watchlist_route": "POST /api/candidate-radar/scan-quick",
        "recommended_custom_pool_route": "POST /api/candidate-radar/scan-quick",
        "recommended_full_pool_local_route": "POST /api/candidate-radar/full-pool-local-scan",
        "recommended_deep_scan_local_review_route": "POST /api/candidate-radar/deep-scan-local-review",
        "recommended_worker_full_pool_route": worker_recipe.get("recommended_worker_full_pool_route")
        or CANDIDATE_FULL_POOL_WORKER_FALLBACK_ROUTE,
        "recommended_worker_deep_scan_route": worker_recipe.get("recommended_worker_deep_scan_route")
        or CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_ROUTE,
        "worker_execution_request_route": CANDIDATE_WORKER_EXECUTION_REQUEST_ROUTE,
        "provider_parity_dry_run_route": "POST /api/candidate-radar/provider-parity-dry-run",
        "quant_projection_acceptance_dry_run_route": "POST /api/candidate-radar/quant-projection-acceptance-dry-run",
        "quant_projection_execution_request_route": QUANT_PROJECTION_EXECUTION_REQUEST_ROUTE,
        "browser_qa_review_route": "POST /api/candidate-radar/browser-qa-review",
        "allowed_next_step": "user_confirmed_post_candidate_radar_quick_scan_or_watchlist_custom_scan"
        if ready_for_user_fast_scan
        else "resolve_local_candidate_radar_fast_scan_blockers",
        "recommended_execution_order": [
            "render cached radar without scanning",
            "run button-gated quick/watchlist/custom scan",
            "review no-feature-loss and result-delta rows",
            "run button-gated full-pool local scan when universe is larger",
            "run button-gated deep-scan local review for parity gaps",
            "review worker execution recipe before any full-pool/deep-scan production task",
            "create a worker execution request ticket bound to the current worker recipe hash",
            "run provider parity and quant projection dry-runs before real provider/model acceptance",
            "create a quant projection execution request ticket bound to the current dry-run scope hash",
            "run browser QA runner and button-gated review",
            "use promotion/activation audits before retiring legacy fallback",
        ],
        "not_allowed_next_steps": [
            "scan market from GET cache or React render",
            "treat quick scan as production radar replacement",
            "treat local full-pool scan as provider-backed full-pool acceptance",
            "treat local deep review as DeepSeek/provider deep scan",
            "treat worker execution recipe as worker execution done",
            "call Tushare/DeepSeek/GitHub from render",
            "treat candidate rows as buy instructions",
            "modify strategy action or holdings",
            "retire legacy radar fallback before promotion audit clears",
        ],
        "required_evidence_before_production_replacement": [
            "worker-backed full-pool execution evidence",
            "worker-backed deep-scan execution evidence",
            "provider-backed parity call ledger",
            "searched-symbol Tushare/DeepSeek acceptance ledger when enabled",
            "browser visual and performance QA promotion",
            "legacy retirement review",
        ],
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "worker_execution_recipe_ready": worker_recipe_ready,
        "worker_execution_implemented": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "page_render_starts_scan": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "blocking_row_count": len(blocking_rows),
        "blocking_phases": [row["phase"] for row in blocking_rows],
        "production_pending_phase_count": len(production_pending_phases),
        "production_pending_phases": production_pending_phases,
        "rows": rows,
        "note": "This recipe organizes the next safe Candidate Radar steps. It does not run scans, call providers/models, produce buy instructions, retire legacy fallback, or complete production replacement.",
    }
    return contract, rows


def _attach_candidate_radar_next_execution_recipe(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_next_execution_recipe(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_next_execution_row_count"] = contract["row_count"]
    counts["candidate_radar_next_execution_blocker_count"] = contract["blocking_row_count"]
    counts["candidate_radar_next_execution_production_pending_count"] = contract["production_pending_phase_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_next_execution_recipe_is_local"] = True
    policy["candidate_radar_next_execution_recipe_calls_provider_or_model"] = False
    policy["candidate_radar_next_execution_recipe_requires_button_task"] = True
    policy["candidate_radar_next_execution_recipe_is_not_production_replacement"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_next_execution_recipe",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=contract["status"],
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_next_execution_recipe"] = contract
    view["candidate_radar_next_execution_rows"] = rows
    return view


def _candidate_radar_durable_evidence_recipe_row(
    evidence_key: str,
    category: str,
    status: str,
    *,
    passed: bool,
    local_surface_required: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_RADAR_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "evidence_key": evidence_key,
        "label": CANDIDATE_RADAR_DURABLE_EVIDENCE_LABELS[evidence_key],
        "category": category,
        "status": status,
        "passed": bool(passed),
        "local_surface_required": bool(local_surface_required),
        "production_blocker": bool(production_blocker),
        "recommended_order": recommended_order,
        "evidence": evidence,
        "next_action": next_action,
        "recipe_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_durable_evidence_recipe(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    policy = _as_dict(packet.get("policy"))
    task_pipeline = _as_dict(packet.get("fast_scan_task_pipeline_contract"))
    legacy_receipt = _as_dict(packet.get("legacy_parity_acceptance_receipt"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    full_pool_receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan_receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    worker_request = _as_dict(packet.get("candidate_radar_worker_execution_request_receipt"))
    provider_parity_dry_run = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    quant_dry_run = _as_dict(packet.get("search_quant_projection_acceptance_dry_run_receipt"))
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    quant_provider_acceptance = _as_dict(packet.get("search_quant_provider_model_acceptance_receipt"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))
    activation = _as_dict(packet.get("candidate_radar_production_activation_receipt"))
    browser_evidence = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    legacy_retirement_review = _as_dict(packet.get("candidate_radar_legacy_retirement_review_receipt"))
    production_promotion_review = _as_dict(packet.get("candidate_radar_production_promotion_review_receipt"))

    cache_render_safe = bool(
        packet.get("cache_only") is True
        and packet.get("read_only") is True
        and policy.get("does_not_scan_market") is True
        and policy.get("post_task_required_for_scan") is True
        and policy.get("does_not_call_tushare") is True
        and policy.get("does_not_call_deepseek") is True
        and policy.get("does_not_call_github") is True
    )
    quick_pipeline_ready = task_pipeline.get("local_task_pipeline_ready") is True
    legacy_receipt_ready = legacy_receipt.get("local_acceptance_receipt_ready") is True
    no_loss_ready = no_loss.get("local_no_feature_loss_contract_ready") is True
    result_delta_ready = result_delta.get("local_result_delta_clarity_ready") is True
    local_full_pool_visible = (
        full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
    )
    local_deep_review_visible = (
        deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
    )
    worker_recipe_visible = worker_recipe.get("local_worker_execution_recipe_ready") is True
    worker_request_visible = worker_request.get("local_execution_request_ready") is True
    provider_ticket_visible = bool(provider_parity_dry_run.get("acceptance_scope_hash_short"))
    quant_ticket_visible = bool(quant_dry_run.get("acceptance_scope_hash_short"))
    quant_request_visible = quant_request.get("local_execution_request_ready") is True
    worker_transport_roundtrip = _read_candidate_worker_filesystem_roundtrip_evidence()
    worker_transport_roundtrip_ready = _candidate_worker_filesystem_roundtrip_ready(worker_transport_roundtrip)
    full_pool_worker_done = bool(
        activation.get("full_pool_scan_done") is True
        or (
            worker_transport_roundtrip_ready
            and worker_transport_roundtrip.get("worker_backed_local_full_pool_scan_done") is True
        )
    )
    deep_scan_worker_done = bool(
        activation.get("deep_scan_done") is True
        or (
            worker_transport_roundtrip_ready
            and worker_transport_roundtrip.get("worker_backed_local_deep_scan_fallback_done") is True
        )
    )
    provider_backed_done = activation.get("provider_backed_acceptance_done") is True
    provider_parity_tushare_light_evidence = _read_candidate_provider_parity_tushare_light_evidence()
    provider_parity_call_ledger_done = _candidate_provider_parity_tushare_light_evidence_ready(
        provider_parity_tushare_light_evidence
    )
    search_quant_provider_model_evidence_done = bool(
        quant_provider_acceptance.get("schema_version") == QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION
        and quant_provider_acceptance.get("direct_evidence_verified") is True
        and quant_provider_acceptance.get("tushare_call_ledger_evidence_done") is True
        and quant_provider_acceptance.get("deepseek_skipped_by_request") is True
        and quant_provider_acceptance.get("production_quant_projection_complete") is False
        and quant_provider_acceptance.get("production_radar_replacement_complete") is False
    )
    provider_call_ledger_evidence_done = bool(
        provider_parity_call_ledger_done or search_quant_provider_model_evidence_done
    )
    local_browser_visual_perf_reviewed = bool(
        browser_evidence.get("candidate_visual_qa_evidence_passed") is True
        and browser_evidence.get("candidate_browser_performance_evidence_passed") is True
        and browser_review.get("local_browser_qa_review_ready") is True
        and promotion.get("browser_evidence_blocker_count") == 0
    )
    browser_visual_perf_done = local_browser_visual_perf_reviewed
    deepseek_model_ledger_done = False
    legacy_retirement_ready = promotion.get("legacy_retirement_ready") is True
    legacy_retirement_review_done = legacy_retirement_review.get("local_review_ready") is True
    promotion_ready = promotion.get("promotion_ready") is True
    production_promotion_review_done = production_promotion_review.get("local_review_ready") is True
    no_trade_boundary = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("does_not_modify_holdings") is not False
        and packet.get("candidate_is_not_buy_instruction") is not False
        and packet.get("contains_secret") is False
    )

    rows = [
        _candidate_radar_durable_evidence_recipe_row(
            "cache_render_boundary_visible",
            "local_surface",
            "passed_cache_render_silent" if cache_render_safe else "blocked_cache_render_boundary",
            passed=cache_render_safe,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"cache_only={packet.get('cache_only')}; post_task_required={policy.get('post_task_required_for_scan')}",
            next_action="Keep Candidate Radar GET/cache/render paths read-only and scan-silent.",
            recommended_order=1,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "quick_scan_task_pipeline_visible",
            "local_surface",
            "passed_local_task_pipeline" if quick_pipeline_ready else "blocked_task_pipeline",
            passed=quick_pipeline_ready,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"task_pipeline_status={task_pipeline.get('status')}; local_ready={quick_pipeline_ready}",
            next_action="Keep quick/watchlist/custom scans behind explicit POST tasks.",
            recommended_order=2,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "legacy_parity_inventory_visible",
            "local_surface",
            "passed_legacy_parity_receipt" if legacy_receipt_ready else "blocked_legacy_parity_receipt",
            passed=legacy_receipt_ready,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"legacy_status={legacy_receipt.get('status')}; blockers={legacy_receipt.get('production_blocker_count')}",
            next_action="Keep Top/Watch/Excluded, evidence links, score dimensions, triggers, filters, fallback, and manual deep research parity visible.",
            recommended_order=3,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "no_feature_loss_surface_visible",
            "local_surface",
            "passed_no_feature_loss_surface" if no_loss_ready else "blocked_no_feature_loss_surface",
            passed=no_loss_ready,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"no_loss_status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            next_action="Report every missing radar behavior instead of hiding or inventing it.",
            recommended_order=4,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "result_delta_clarity_visible",
            "local_surface",
            "passed_delta_surface" if result_delta_ready else "pending_delta_surface",
            passed=result_delta_ready,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"delta_status={result_delta.get('status')}; previous_diff={result_delta.get('previous_cache_diff_done')}",
            next_action="Keep changed/added/removed/rank-delta visibility for user clarity.",
            recommended_order=5,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "local_full_pool_receipt_visible",
            "local_surface",
            "passed_local_receipt_visible" if local_full_pool_visible else "pending_local_full_pool_receipt",
            passed=local_full_pool_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"local_full_pool_execution_done={full_pool_receipt.get('local_full_pool_execution_done')}; worker_done={full_pool_receipt.get('worker_backed_execution_done')}",
            next_action="Use local full-pool receipt only as shape evidence before real worker execution.",
            recommended_order=6,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "local_deep_scan_review_visible",
            "local_surface",
            "passed_local_review_visible" if local_deep_review_visible else "pending_local_deep_review",
            passed=local_deep_review_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"local_deep_scan_review_done={deep_scan_receipt.get('local_deep_scan_review_done')}; deep_scan_done={deep_scan_receipt.get('deep_scan_done')}",
            next_action="Use local deep review only as parity evidence before real deep-scan execution.",
            recommended_order=7,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "worker_execution_recipe_visible",
            "local_surface",
            "passed_worker_recipe" if worker_recipe_visible else "pending_worker_recipe",
            passed=worker_recipe_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"worker_recipe_status={worker_recipe.get('status')}; blockers={worker_recipe.get('production_blocker_count')}",
            next_action="Keep full-pool/deep-scan production execution behind worker task evidence.",
            recommended_order=8,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "worker_execution_request_visible",
            "durable_evidence",
            "scope_request_visible" if worker_request_visible else "pending_worker_execution_request",
            passed=worker_request_visible,
            local_surface_required=False,
            production_blocker=not worker_request_visible,
            evidence=f"worker_request_status={worker_request.get('status')}; scope={worker_request.get('worker_execution_scope_hash_short') or 'missing'}",
            next_action="Create a button-gated worker execution request before implementing the future worker-backed radar scan.",
            recommended_order=9,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "provider_parity_scope_ticket_required",
            "durable_evidence",
            "scope_ticket_visible" if provider_ticket_visible else "pending_provider_parity_dry_run",
            passed=provider_ticket_visible,
            local_surface_required=False,
            production_blocker=not provider_ticket_visible,
            evidence=f"provider_parity_status={provider_parity_dry_run.get('status')}; scope={provider_parity_dry_run.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Create a user-approved provider parity dry-run scope ticket before any real provider-backed radar acceptance.",
            recommended_order=10,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "quant_projection_scope_ticket_required",
            "durable_evidence",
            "scope_ticket_visible" if quant_ticket_visible else "pending_quant_projection_dry_run",
            passed=quant_ticket_visible,
            local_surface_required=False,
            production_blocker=not quant_ticket_visible,
            evidence=f"quant_dry_run_status={quant_dry_run.get('status')}; scope={quant_dry_run.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Bind searched-symbol Tushare/DeepSeek acceptance to a user-approved dry-run scope.",
            recommended_order=11,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "quant_projection_execution_request_visible",
            "durable_evidence",
            "scope_request_visible" if quant_request_visible else "pending_quant_projection_execution_request",
            passed=quant_request_visible,
            local_surface_required=False,
            production_blocker=not quant_request_visible,
            evidence=f"quant_request_status={quant_request.get('status')}; scope={quant_request.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Create a button-gated quant projection execution request before future Tushare/DeepSeek execution.",
            recommended_order=12,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "worker_full_pool_execution_evidence_required",
            "durable_evidence",
            "completed" if full_pool_worker_done else "pending_worker_full_pool_execution",
            passed=full_pool_worker_done,
            local_surface_required=False,
            production_blocker=not full_pool_worker_done,
            evidence=(
                f"full_pool_scan_done={activation.get('full_pool_scan_done') is True}; "
                f"filesystem_worker_roundtrip={worker_transport_roundtrip_ready}; "
                f"task_id={worker_transport_roundtrip.get('returned_task_id') or ''}; "
                f"call_api={worker_transport_roundtrip.get('returned_call_api') or ''}; "
                f"row_count={worker_transport_roundtrip.get('returned_call_row_count') or 0}; "
                "production_full_pool_scan_done=false"
            ),
            next_action="Run future worker-backed full-pool task and attach durable task/call/coverage evidence.",
            recommended_order=13,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "worker_deep_scan_execution_evidence_required",
            "durable_evidence",
            "completed" if deep_scan_worker_done else "pending_worker_deep_scan_execution",
            passed=deep_scan_worker_done,
            local_surface_required=False,
            production_blocker=not deep_scan_worker_done,
            evidence=(
                f"deep_scan_done={activation.get('deep_scan_done') is True}; "
                f"filesystem_worker_roundtrip={worker_transport_roundtrip_ready}; "
                f"task_id={worker_transport_roundtrip.get('deep_scan_returned_task_id') or ''}; "
                f"call_api={worker_transport_roundtrip.get('deep_scan_returned_call_api') or ''}; "
                f"row_count={worker_transport_roundtrip.get('deep_scan_returned_call_row_count') or 0}; "
                "production_deep_scan_done=false"
            ),
            next_action="Run future worker-backed deep scan with provider/model boundaries and safe failure rows.",
            recommended_order=14,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "provider_backed_parity_call_ledger_required",
            "durable_evidence",
            "provider_call_ledger_observed"
            if provider_call_ledger_evidence_done
            else "pending_provider_call_ledger",
            passed=provider_call_ledger_evidence_done,
            local_surface_required=False,
            production_blocker=not provider_call_ledger_evidence_done,
            evidence=(
                f"provider_backed_acceptance_done={provider_backed_done}; "
                f"provider_parity_call_ledger_evidence_done={provider_parity_call_ledger_done}; "
                f"search_quant_provider_model_evidence_done={search_quant_provider_model_evidence_done}; "
                f"api_success={provider_parity_tushare_light_evidence.get('api_success_count') or 0}/"
                f"{provider_parity_tushare_light_evidence.get('api_call_count') or 0}"
            ),
            next_action="Record real provider call ledger rows for selected radar signal groups before promotion.",
            recommended_order=15,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "browser_visual_performance_evidence_required",
            "durable_evidence",
            "reviewed" if browser_visual_perf_done else "pending_browser_visual_performance",
            passed=browser_visual_perf_done,
            local_surface_required=False,
            production_blocker=not browser_visual_perf_done,
            evidence=f"local_reviewed={local_browser_visual_perf_reviewed}; visual={browser_evidence.get('candidate_visual_qa_evidence_passed')}; perf={browser_evidence.get('candidate_browser_performance_evidence_passed')}; review={browser_review.get('local_browser_qa_review_ready')}; durable_promotion=false",
            next_action="Keep local browser visual/performance review visible; durable CI/release promotion still belongs to production review.",
            recommended_order=16,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "deepseek_model_ledger_if_enabled_required",
            "durable_evidence",
            "pending_optional_model_ledger",
            passed=deepseek_model_ledger_done,
            local_surface_required=False,
            production_blocker=True,
            evidence="DeepSeek is not called by the recipe; future deep research must include model ledger, sanitizer, hashes, token usage, and parse_failed discard.",
            next_action="Only attach DeepSeek evidence from explicit button/task execution, never from render.",
            recommended_order=17,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "legacy_retirement_review_required",
            "durable_evidence",
            "ready_for_legacy_retirement"
            if legacy_retirement_ready
            else "review_visible_retirement_blocked"
            if legacy_retirement_review_done
            else "pending_legacy_retirement_review",
            passed=legacy_retirement_ready or legacy_retirement_review_done,
            local_surface_required=False,
            production_blocker=not (legacy_retirement_ready or legacy_retirement_review_done),
            evidence=(
                f"legacy_retirement_review_done={legacy_retirement_review_done}; "
                f"legacy_retirement_ready={legacy_retirement_ready}; "
                f"ready_to_retire_legacy={legacy_retirement_review.get('ready_to_retire_legacy') is True}"
            ),
            next_action="Keep Streamlit radar fallback until worker/provider/browser promotion clears.",
            recommended_order=18,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "production_promotion_review_required",
            "durable_evidence",
            "ready_for_promotion"
            if promotion_ready
            else "review_visible_production_blocked"
            if production_promotion_review_done
            else "pending_promotion_review",
            passed=promotion_ready or production_promotion_review_done,
            local_surface_required=False,
            production_blocker=not (promotion_ready or production_promotion_review_done),
            evidence=(
                f"production_promotion_review_done={production_promotion_review_done}; "
                f"promotion_ready={promotion_ready}; blockers={promotion.get('blocking_promotion_count')}"
            ),
            next_action="Promote only after direct worker/provider/browser/model evidence and redaction review.",
            recommended_order=19,
        ),
        _candidate_radar_durable_evidence_recipe_row(
            "no_trade_action_secret_boundary",
            "safety",
            "passed_research_only_secret_safe" if no_trade_boundary else "blocked_safety_boundary",
            passed=no_trade_boundary,
            local_surface_required=True,
            production_blocker=not no_trade_boundary,
            evidence="Candidate Radar does not execute trades, mutate action/holdings, expose secrets, or turn candidates into buy instructions.",
            next_action="Keep radar outputs research-only even after production evidence improves.",
            recommended_order=20,
        ),
    ]
    local_blockers = [row["evidence_key"] for row in rows if row["local_surface_required"] and not row["passed"]]
    durable_blockers = [row["evidence_key"] for row in rows if row["production_blocker"] and not row["passed"]]
    local_ready = not local_blockers
    contract = {
        "schema_version": CANDIDATE_RADAR_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "candidate_radar_durable_evidence_recipe_ready_production_pending"
            if local_ready
            else "candidate_radar_durable_evidence_recipe_blocked_local_surface"
        ),
        "scope": "local_candidate_radar_durable_evidence_recipe_no_scan_or_provider_call",
        "ltg": "LTG-13/LTG-14/LTG-02/LTG-07",
        "local_recipe_ready": local_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": full_pool_worker_done,
        "deep_scan_done": deep_scan_worker_done,
        "provider_backed_acceptance_done": provider_backed_done,
        "provider_parity_call_ledger_evidence_done": provider_parity_call_ledger_done,
        "search_quant_provider_model_evidence_done": search_quant_provider_model_evidence_done,
        "provider_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "browser_visual_performance_reviewed": browser_visual_perf_done,
        "deepseek_model_ledger_complete": deepseek_model_ledger_done,
        "legacy_retirement_review_done": legacy_retirement_review_done,
        "production_promotion_review_done": production_promotion_review_done,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_execution_implemented": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "page_render_starts_scan": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "evidence_keys": list(CANDIDATE_RADAR_DURABLE_EVIDENCE_KEYS),
        "missing_durable_evidence": durable_blockers,
        "required_evidence": [
            "user-approved provider parity scope ticket",
            "button-gated worker execution request ticket bound to the worker recipe hash",
            "searched-symbol quant projection scope ticket when used",
            "button-gated quant projection execution request ticket bound to the dry-run scope hash",
            "worker-backed full-pool execution task evidence",
            "worker-backed deep-scan execution task evidence",
            "real provider call ledger for selected radar signal groups",
            "DeepSeek model ledger and sanitizer evidence when enabled",
            "browser visual/performance evidence for #candidates",
            "legacy fallback retirement review",
            "production promotion and redaction review",
        ],
        "not_allowed_next_steps": [
            "treat durable recipe as production radar replacement",
            "treat quick scan as no-feature-loss production completion",
            "treat local full-pool receipt as worker full-pool execution",
            "treat local deep review as DeepSeek/provider deep scan",
            "call Tushare or DeepSeek from GET cache or React render",
            "retire legacy radar fallback from local recipe evidence",
            "turn candidate score into buy/sell instruction",
            "mutate strategy action, price, holdings, or operation zones",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "allowed_next_step": "run_user_approved_scope_dry_runs_then_worker_provider_browser_acceptance",
        "row_count": len(rows),
        "evidence_key_count": len(CANDIDATE_RADAR_DURABLE_EVIDENCE_KEYS),
        "local_blocker_count": len(local_blockers),
        "durable_evidence_blocker_count": len(durable_blockers),
        "production_blocker_count": len(durable_blockers),
        "local_blockers": local_blockers,
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This recipe fixes the durable evidence checklist for LTG-13. It does not execute scans, start workers, call providers/models, retire legacy radar, or complete production replacement.",
    }
    return contract, rows


def _attach_candidate_radar_durable_evidence_recipe(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_durable_evidence_recipe(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_durable_evidence_row_count"] = contract["row_count"]
    counts["candidate_radar_durable_evidence_blocker_count"] = contract["durable_evidence_blocker_count"]
    counts["candidate_radar_durable_evidence_ready"] = contract["local_recipe_ready"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_durable_evidence_recipe_is_local"] = True
    policy["candidate_radar_durable_evidence_recipe_calls_provider_or_model"] = False
    policy["candidate_radar_durable_evidence_recipe_is_not_production_replacement"] = True
    policy["candidate_radar_durable_evidence_requires_worker_provider_browser_model_evidence"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_durable_evidence_recipe",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=contract["status"],
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar durable evidence recipe 只固定下一票雷达生产替代证据清单；不会运行扫描、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_durable_evidence_recipe"] = contract
    view["candidate_radar_durable_evidence_rows"] = rows
    return view


def _read_candidate_worker_filesystem_roundtrip_evidence() -> dict[str, Any]:
    try:
        payload = json.loads(CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_candidate_provider_parity_tushare_light_evidence() -> dict[str, Any]:
    try:
        payload = json.loads(CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_provider_parity_tushare_light_evidence_ready(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("schema_version") == "candidate_radar_provider_parity_tushare_light_evidence.v1"
        and payload.get("status") == "candidate_radar_provider_parity_tushare_light_evidence_ready"
        and payload.get("direct_evidence_layer")
        == "L3_real_tushare_provider_call_ledger_supporting_candidate_radar_provider_parity"
        and int(payload.get("candidate_count") or 0) > 0
        and int(payload.get("api_call_count") or 0) > 0
        and int(payload.get("api_terminal_ok_count") or payload.get("api_success_count") or 0)
        == int(payload.get("api_call_count") or 0)
        and int(payload.get("api_failed_count") or 0) == 0
        and (
            payload.get("all_selected_api_calls_terminal_ok") is True
            or payload.get("all_selected_api_calls_succeeded") is True
        )
        and payload.get("has_core_light_samples_for_all_candidates") is True
        and payload.get("has_trade_cal_sample") is True
        and payload.get("external_calls_triggered") is True
        and payload.get("tushare_called") is True
        and payload.get("deepseek_called") is False
        and payload.get("github_called") is False
        and payload.get("deepseek_model_execution_done") is False
        and payload.get("provider_backed_acceptance_done") is False
        and payload.get("production_radar_replacement_complete") is False
        and payload.get("does_not_execute_trades") is True
        and payload.get("does_not_modify_strategy_action") is True
        and payload.get("contains_secret") in (False, None)
    )


def _candidate_worker_filesystem_roundtrip_ready(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("schema_version") == "candidate_radar_worker_filesystem_roundtrip_smoke.v1"
        and payload.get("status") == "candidate_radar_worker_filesystem_roundtrip_passed"
        and payload.get("direct_evidence_layer")
        == "L3_local_candidate_radar_worker_filesystem_roundtrip_not_redis"
        and payload.get("candidate_task_type") == "run_candidate_radar_full_pool_local_scan"
        and payload.get("output_packet_key") == "command_center_3_candidate_radar_cache"
        and payload.get("task_dispatched") is True
        and payload.get("task_result_returned") is True
        and payload.get("worker_backed_local_full_pool_scan_done") is True
        and payload.get("returned_current_step") == "candidate_radar_full_pool_local_scan_completed"
        and payload.get("returned_call_api") == "local_candidate_radar_full_pool_local_scan"
        and int(payload.get("returned_call_row_count") or 0) > 0
        and payload.get("worker_backed_local_deep_scan_fallback_done") is True
        and payload.get("deep_scan_returned_current_step") == "candidate_radar_deep_scan_worker_fallback_ready"
        and payload.get("deep_scan_returned_call_api") == "local_candidate_radar_deep_scan_worker_fallback"
        and int(payload.get("deep_scan_returned_call_row_count") or 0) > 0
        and payload.get("filesystem_broker_used") is True
        and payload.get("redis_broker_used") is False
        and payload.get("redis_pinged") is False
        and payload.get("production_worker_complete") is False
        and payload.get("production_radar_replacement_complete") is False
        and payload.get("production_full_pool_scan_done") is False
        and payload.get("production_deep_scan_done") is False
        and payload.get("deepseek_model_execution_done") is False
        and payload.get("provider_backed_acceptance_done") is False
        and payload.get("external_calls_triggered") is False
        and payload.get("tushare_called") is False
        and payload.get("deepseek_called") is False
        and payload.get("github_called") is False
        and payload.get("does_not_execute_trades") is True
        and payload.get("does_not_modify_strategy_action") is True
        and payload.get("candidate_is_not_buy_instruction") is True
        and payload.get("contains_secret") is False
    )


def _candidate_radar_production_stage_scope_manifest(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    policy = _as_dict(packet.get("policy"))
    fast_pipeline = _as_dict(packet.get("fast_scan_task_pipeline_contract"))
    full_pool = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan = _as_dict(packet.get("deep_scan_local_review_receipt"))
    worker_runtime_link = _as_dict(packet.get("candidate_radar_worker_runtime_linked_evidence"))
    full_pool_worker = _as_dict(packet.get("candidate_radar_full_pool_worker_fallback_receipt"))
    deep_scan_worker = _as_dict(packet.get("candidate_radar_deep_scan_worker_fallback_receipt"))
    provider_dry_run = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    quant_provider_acceptance = _as_dict(packet.get("search_quant_provider_model_acceptance_receipt"))
    browser_evidence = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))
    production_review = _as_dict(packet.get("candidate_radar_production_replacement_review_receipt"))
    production_promotion = _as_dict(packet.get("candidate_radar_production_promotion_review_receipt"))
    legacy_review = _as_dict(packet.get("candidate_radar_legacy_retirement_review_receipt"))

    cache_render_ready = bool(
        packet.get("cache_only") is True
        and packet.get("read_only") is True
        and policy.get("does_not_scan_market") is True
        and policy.get("post_task_required_for_scan") is True
        and policy.get("does_not_call_tushare") is True
        and policy.get("does_not_call_deepseek") is True
        and policy.get("does_not_call_github") is True
        and packet.get("external_calls_triggered") is False
    )
    quick_pipeline_ready = fast_pipeline.get("local_task_pipeline_ready") is True
    local_full_pool_ready = full_pool.get("local_full_pool_execution_done") is True
    local_deep_scan_ready = deep_scan.get("local_deep_scan_review_done") is True
    worker_runtime_round_trip_ready = (
        worker_runtime_link.get("schema_version") == CANDIDATE_WORKER_RUNTIME_LINKED_EVIDENCE_SCHEMA_VERSION
        and worker_runtime_link.get("status") == "candidate_radar_worker_runtime_local_evidence_linked"
        and worker_runtime_link.get("worker_runtime_local_evidence_linked") is True
        and worker_runtime_link.get("local_fallback_round_trip_verified") is True
        and worker_runtime_link.get("task_log_round_trip_verified") is True
        and worker_runtime_link.get("append_only_worker_log_verified") is True
        and worker_runtime_link.get("cross_process_task_control_verified") is True
        and worker_runtime_link.get("scheduler_default_off_runtime_verified") is True
        and worker_runtime_link.get("provider_model_no_autoschedule_boundary_verified") is True
        and worker_runtime_link.get("production_worker_complete") is False
        and worker_runtime_link.get("worker_started") is False
        and worker_runtime_link.get("celery_worker_started") is False
        and worker_runtime_link.get("redis_broker_used") is False
        and worker_runtime_link.get("production_radar_replacement_complete") is False
        and worker_runtime_link.get("worker_full_pool_execution_done") is False
        and worker_runtime_link.get("worker_deep_scan_execution_done") is False
        and worker_runtime_link.get("provider_backed_acceptance_done") is False
        and worker_runtime_link.get("external_calls_triggered") is False
        and worker_runtime_link.get("tushare_called") is False
        and worker_runtime_link.get("deepseek_called") is False
        and worker_runtime_link.get("github_called") is False
        and worker_runtime_link.get("does_not_execute_trades") is True
        and worker_runtime_link.get("does_not_modify_strategy_action") is True
        and worker_runtime_link.get("candidate_is_not_buy_instruction") is True
        and worker_runtime_link.get("contains_secret") is False
    )
    worker_full_pool_fallback_visible = (
        full_pool_worker.get("local_worker_fallback_full_pool_done") is True
        and full_pool_worker.get("worker_started") is False
        and full_pool_worker.get("provider_backed_acceptance_done") is False
    )
    worker_deep_scan_fallback_visible = (
        deep_scan_worker.get("local_deep_scan_review_done") is True
        and deep_scan_worker.get("worker_started") is False
        and deep_scan_worker.get("provider_backed_acceptance_done") is False
    )
    worker_transport_roundtrip = _read_candidate_worker_filesystem_roundtrip_evidence()
    worker_transport_roundtrip_ready = _candidate_worker_filesystem_roundtrip_ready(worker_transport_roundtrip)
    provider_parity_tushare_light_evidence = _read_candidate_provider_parity_tushare_light_evidence()
    provider_parity_tushare_light_ready = _candidate_provider_parity_tushare_light_evidence_ready(
        provider_parity_tushare_light_evidence
    )
    worker_full_pool_execution_ready = (
        full_pool_worker.get("worker_backed_execution_done") is True
        and full_pool_worker.get("worker_task_executed") is True
        and full_pool_worker.get("worker_execution_implemented") is True
        and full_pool_worker.get("production_full_pool_scan_done") is True
    ) or (
        worker_transport_roundtrip_ready
        and worker_transport_roundtrip.get("worker_backed_local_full_pool_scan_done") is True
    )
    worker_deep_scan_execution_ready = (
        deep_scan_worker.get("worker_backed_execution_done") is True
        and deep_scan_worker.get("worker_task_executed") is True
        and deep_scan_worker.get("worker_execution_implemented") is True
        and deep_scan_worker.get("production_deep_scan_done") is True
    ) or (
        worker_transport_roundtrip_ready
        and worker_transport_roundtrip.get("worker_backed_local_deep_scan_fallback_done") is True
    )
    provider_parity_ready = provider_parity_tushare_light_ready
    search_quant_ready = bool(
        quant_provider_acceptance.get("schema_version") == QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION
        and quant_provider_acceptance.get("direct_evidence_verified") is True
        and quant_provider_acceptance.get("tushare_call_ledger_evidence_done") is True
        and quant_provider_acceptance.get("deepseek_skipped_by_request") is True
        and quant_provider_acceptance.get("production_quant_projection_complete") is False
        and quant_provider_acceptance.get("production_radar_replacement_complete") is False
    )
    browser_promotion_ready = bool(
        production_review.get("browser_visual_performance_promoted") is True
        or production_promotion.get("browser_visual_performance_promoted") is True
        or (
            browser_evidence.get("candidate_visual_qa_evidence_passed") is True
            and browser_evidence.get("candidate_browser_performance_evidence_passed") is True
            and browser_review.get("local_browser_qa_review_ready") is True
            and int(promotion.get("browser_evidence_blocker_count") or 0) == 0
        )
    )
    legacy_review_ready = legacy_review.get("local_review_ready") is True
    production_promotion_review_ready = production_promotion.get("local_review_ready") is True
    stage_state = {
        "cache_render_boundary": {
            "direct": cache_render_ready,
            "status": "direct_evidence_ready_cache_render_boundary" if cache_render_ready else "direct_evidence_pending",
            "evidence": f"cache_only={packet.get('cache_only')}; post_task_required={policy.get('post_task_required_for_scan')}",
            "missing": [] if cache_render_ready else ["cache/render no-scan boundary evidence"],
        },
        "quick_scan_task_pipeline": {
            "direct": quick_pipeline_ready,
            "status": "direct_evidence_ready_quick_scan_pipeline" if quick_pipeline_ready else "direct_evidence_pending",
            "evidence": f"fast_pipeline_status={fast_pipeline.get('status')}; local_ready={quick_pipeline_ready}",
            "missing": [] if quick_pipeline_ready else ["button-gated quick scan task pipeline evidence"],
        },
        "local_full_pool_execution_receipt": {
            "direct": local_full_pool_ready,
            "status": "direct_evidence_ready_local_full_pool_receipt" if local_full_pool_ready else "direct_evidence_pending",
            "evidence": f"local_full_pool_execution_done={local_full_pool_ready}",
            "missing": [] if local_full_pool_ready else ["local full-pool receipt"],
        },
        "local_deep_scan_review_receipt": {
            "direct": local_deep_scan_ready,
            "status": "direct_evidence_ready_local_deep_scan_review" if local_deep_scan_ready else "direct_evidence_pending",
            "evidence": f"local_deep_scan_review_done={local_deep_scan_ready}",
            "missing": [] if local_deep_scan_ready else ["local deep-scan review receipt"],
        },
        "worker_runtime_round_trip_link": {
            "direct": worker_runtime_round_trip_ready,
            "status": (
                "direct_evidence_ready_worker_runtime_round_trip_link"
                if worker_runtime_round_trip_ready
                else "worker_runtime_round_trip_link_pending"
            ),
            "evidence": (
                f"worker_runtime_linked={worker_runtime_round_trip_ready}; "
                f"source_status={worker_runtime_link.get('source_worker_runtime_status') or 'missing'}; "
                f"task_id={worker_runtime_link.get('worker_runtime_execution_task_id') or ''}"
            ),
            "missing": [] if worker_runtime_round_trip_ready else ["local worker runtime round-trip link"],
        },
        "worker_transport_round_trip_smoke": {
            "direct": worker_transport_roundtrip_ready,
            "status": (
                "direct_evidence_ready_candidate_worker_filesystem_roundtrip"
                if worker_transport_roundtrip_ready
                else "candidate_worker_filesystem_roundtrip_evidence_missing"
            ),
            "evidence": (
                f"artifact={CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH}; "
                f"status={worker_transport_roundtrip.get('status') or 'missing'}; "
                f"task_id={worker_transport_roundtrip.get('returned_task_id') or ''}; "
                f"call_api={worker_transport_roundtrip.get('returned_call_api') or ''}; "
                f"row_count={worker_transport_roundtrip.get('returned_call_row_count') or 0}; "
                f"deep_scan_task_id={worker_transport_roundtrip.get('deep_scan_returned_task_id') or ''}; "
                f"deep_scan_call_api={worker_transport_roundtrip.get('deep_scan_returned_call_api') or ''}; "
                f"deep_scan_row_count={worker_transport_roundtrip.get('deep_scan_returned_call_row_count') or 0}; "
                "redis_broker_used=false; production_worker_complete=false"
            ),
            "missing": (
                []
                if worker_transport_roundtrip_ready
                else ["candidate radar local worker filesystem round-trip evidence artifact"]
            ),
        },
        "local_worker_full_pool_fallback_receipt": {
            "direct": worker_full_pool_fallback_visible,
            "status": (
                "direct_evidence_ready_local_full_pool_worker_fallback"
                if worker_full_pool_fallback_visible
                else "local_worker_fallback_receipt_pending"
            ),
            "evidence": (
                f"local_worker_fallback_full_pool_done={worker_full_pool_fallback_visible}; "
                "real_worker_done=false"
            ),
            "missing": [] if worker_full_pool_fallback_visible else ["local full-pool worker-fallback receipt"],
            "local_worker_fallback_evidence_present": worker_full_pool_fallback_visible,
        },
        "local_worker_deep_scan_fallback_receipt": {
            "direct": worker_deep_scan_fallback_visible,
            "status": (
                "direct_evidence_ready_local_deep_scan_worker_fallback"
                if worker_deep_scan_fallback_visible
                else "local_worker_fallback_receipt_pending"
            ),
            "evidence": (
                f"local_worker_deep_scan_fallback_done={worker_deep_scan_fallback_visible}; "
                "real_worker_done=false"
            ),
            "missing": [] if worker_deep_scan_fallback_visible else ["local deep-scan worker-fallback receipt"],
            "local_worker_fallback_evidence_present": worker_deep_scan_fallback_visible,
        },
        "worker_full_pool_execution": {
            "direct": worker_full_pool_execution_ready,
            "status": (
                "direct_evidence_ready_local_worker_full_pool_execution"
                if worker_full_pool_execution_ready
                else "local_worker_fallback_visible_real_worker_pending"
                if worker_full_pool_fallback_visible
                else "direct_evidence_pending"
            ),
            "evidence": (
                f"local_worker_fallback_full_pool_done={worker_full_pool_fallback_visible}; "
                f"filesystem_worker_roundtrip={worker_transport_roundtrip_ready}; "
                f"task_id={worker_transport_roundtrip.get('returned_task_id') or ''}; "
                f"call_api={worker_transport_roundtrip.get('returned_call_api') or ''}; "
                f"row_count={worker_transport_roundtrip.get('returned_call_row_count') or 0}; "
                "production_full_pool_scan_done=false"
            ),
            "missing": [] if worker_full_pool_execution_ready else ["worker full-pool execution evidence"],
            "local_worker_fallback_evidence_present": worker_full_pool_fallback_visible,
            "worker_filesystem_roundtrip_evidence_present": worker_transport_roundtrip_ready,
            "worker_backed_execution_done": worker_full_pool_execution_ready,
        },
        "worker_deep_scan_execution": {
            "direct": worker_deep_scan_execution_ready,
            "status": (
                "direct_evidence_ready_local_worker_deep_scan_execution"
                if worker_deep_scan_execution_ready
                else "local_worker_fallback_visible_real_worker_pending"
                if worker_deep_scan_fallback_visible
                else "direct_evidence_pending"
            ),
            "evidence": (
                f"local_worker_deep_scan_fallback_done={worker_deep_scan_fallback_visible}; "
                f"filesystem_worker_roundtrip={worker_transport_roundtrip_ready}; "
                f"task_id={worker_transport_roundtrip.get('deep_scan_returned_task_id') or ''}; "
                f"call_api={worker_transport_roundtrip.get('deep_scan_returned_call_api') or ''}; "
                f"row_count={worker_transport_roundtrip.get('deep_scan_returned_call_row_count') or 0}; "
                "production_deep_scan_done=false"
            ),
            "missing": [] if worker_deep_scan_execution_ready else ["worker deep-scan execution evidence"],
            "local_worker_fallback_evidence_present": worker_deep_scan_fallback_visible,
            "worker_filesystem_roundtrip_evidence_present": worker_transport_roundtrip_ready,
            "worker_backed_execution_done": worker_deep_scan_execution_ready,
        },
        "provider_parity_acceptance": {
            "direct": provider_parity_ready,
            "status": (
                "direct_evidence_ready_tushare_light_provider_parity_ledger"
                if provider_parity_ready
                else "provider_parity_call_ledger_pending"
            ),
            "evidence": (
                f"provider_scope_ticket={provider_dry_run.get('acceptance_scope_hash_short') or 'missing'}; "
                f"artifact={CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH}; "
                f"status={provider_parity_tushare_light_evidence.get('status') or 'missing'}; "
                f"candidate_count={provider_parity_tushare_light_evidence.get('candidate_count') or 0}; "
                f"api_success={provider_parity_tushare_light_evidence.get('api_success_count') or 0}/"
                f"{provider_parity_tushare_light_evidence.get('api_call_count') or 0}; "
                "provider_backed_acceptance_done=false; production_radar_replacement_complete=false"
            ),
            "missing": [] if provider_parity_ready else ["provider-backed parity call ledger"],
            "provider_parity_tushare_light_evidence_present": provider_parity_ready,
        },
        "search_quant_provider_model_acceptance": {
            "direct": search_quant_ready,
            "status": (
                "direct_evidence_ready_tushare_light_deepseek_skipped"
                if search_quant_ready
                else "provider_model_execution_pending"
            ),
            "evidence": (
                f"quant_request={quant_request.get('status') or 'missing'}; "
                f"provider_acceptance={quant_provider_acceptance.get('status') or 'missing'}; "
                f"api_success={quant_provider_acceptance.get('provider_api_success_count') or 0}/"
                f"{quant_provider_acceptance.get('provider_api_call_count') or 0}; "
                "production_quant_projection_complete=false"
            ),
            "missing": [] if search_quant_ready else ["searched-symbol provider/model execution ledger"],
            "tushare_light_provider_evidence_done": search_quant_ready,
        },
        "browser_visual_performance_promotion": {
            "direct": browser_promotion_ready,
            "status": (
                "direct_evidence_ready_browser_visual_performance"
                if browser_promotion_ready
                else "direct_evidence_pending"
            ),
            "evidence": (
                f"browser_visual={browser_evidence.get('candidate_visual_qa_evidence_passed') is True}; "
                f"browser_perf={browser_evidence.get('candidate_browser_performance_evidence_passed') is True}; "
                f"review={browser_review.get('local_browser_qa_review_ready') is True}"
            ),
            "missing": [] if browser_promotion_ready else ["browser visual and performance promotion"],
        },
        "legacy_retirement_review": {
            "direct": legacy_review_ready,
            "status": (
                "direct_evidence_ready_legacy_review_retirement_blocked"
                if legacy_review_ready
                else "direct_evidence_pending"
            ),
            "evidence": f"legacy_retirement_review_visible={legacy_review_ready}; legacy_retirement_ready=false",
            "missing": [] if legacy_review_ready else ["legacy retirement review"],
        },
        "production_promotion_review": {
            "direct": production_promotion_review_ready,
            "status": (
                "direct_evidence_ready_production_promotion_review_blocked"
                if production_promotion_review_ready
                else "direct_evidence_pending"
            ),
            "evidence": (
                f"production_promotion_review_visible={production_promotion_review_ready}; "
                "production_radar_replacement_complete=false"
            ),
            "missing": [] if production_promotion_review_ready else ["production promotion review"],
        },
    }
    rows = []
    for stage_key in CANDIDATE_RADAR_PRODUCTION_STAGE_KEYS:
        state = stage_state[stage_key]
        direct = bool(state["direct"])
        rows.append(
            {
                "schema_version": CANDIDATE_RADAR_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION,
                "stage_key": stage_key,
                "stage_label": CANDIDATE_RADAR_PRODUCTION_STAGE_LABELS[stage_key],
                "scope": "candidate_radar_production_stage_scope_manifest",
                "current_status": state["status"],
                "target_status": "production_replacement_direct_evidence_required",
                "local_stage_evidence_present": stage_key in LOCAL_CANDIDATE_RADAR_STAGE_EVIDENCE_KEYS,
                "local_worker_fallback_evidence_present": bool(
                    state.get("local_worker_fallback_evidence_present")
                ),
                "direct_evidence_complete": direct,
                "direct_evidence_layer": (
                    "L3_real_tushare_provider_call_ledger_supporting_candidate_radar_provider_parity"
                    if stage_key == "provider_parity_acceptance" and direct
                    else "L3_local_candidate_radar_direct_evidence"
                    if direct
                    else ""
                ),
                "required_before_production_replacement": True,
                "production_blocker": not direct,
                "production_radar_replacement_complete": False,
                "legacy_retirement_ready": False,
                "legacy_fallback_required": True,
                "full_pool_scan_done": False,
                "deep_scan_done": False,
                "provider_backed_acceptance_done": False,
                "provider_parity_tushare_light_evidence_present": bool(
                    state.get("provider_parity_tushare_light_evidence_present")
                ),
                "worker_backed_execution_done": bool(state.get("worker_backed_execution_done")),
                "worker_fallback_direct_evidence_done": bool(state.get("worker_fallback_direct_evidence_done")),
                "worker_runtime_round_trip_linked": stage_key == "worker_runtime_round_trip_link" and direct,
                "local_worker_fallback_evidence_done": bool(
                    state.get("local_worker_fallback_evidence_present")
                ),
                "worker_filesystem_roundtrip_evidence_present": bool(
                    state.get("worker_filesystem_roundtrip_evidence_present")
                ),
                "browser_performance_trace_done": stage_key == "browser_visual_performance_promotion" and direct,
                "browser_visual_delta_qa_done": stage_key == "browser_visual_performance_promotion" and direct,
                "durable_ci_evidence_complete": False,
                "provider_execution_implemented": False,
                "model_execution_implemented": False,
                "page_render_starts_full_pool": False,
                "page_render_starts_deep_scan": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
                "contains_secret": False,
                "evidence": state["evidence"],
                "missing_evidence": state["missing"],
            }
        )
    direct_evidence_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is True]
    pending_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is not True]
    local_evidence_count = sum(1 for row in rows if row["local_stage_evidence_present"] is True)
    worker_fallback_evidence_keys = [
        row["stage_key"] for row in rows if row["local_worker_fallback_evidence_present"] is True
    ]
    manifest = {
        "schema_version": CANDIDATE_RADAR_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION,
        "status": "candidate_radar_production_stage_scope_manifest_ready_production_pending",
        "scope": "local_candidate_radar_production_stage_scope_manifest_no_execution",
        "ltg": "LTG-13",
        "local_manifest_ready": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "worker_backed_execution_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "durable_ci_evidence_complete": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "page_render_starts_full_pool": False,
        "page_render_starts_deep_scan": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "stage_keys": list(CANDIDATE_RADAR_PRODUCTION_STAGE_KEYS),
        "row_count": len(rows),
        "stage_key_count": len(CANDIDATE_RADAR_PRODUCTION_STAGE_KEYS),
        "direct_evidence_stage_count": len(direct_evidence_keys),
        "direct_evidence_stage_keys": direct_evidence_keys,
        "pending_stage_count": len(pending_keys),
        "pending_stage_keys": pending_keys,
        "local_evidence_stage_count": local_evidence_count,
        "worker_fallback_evidence_stage_count": len(worker_fallback_evidence_keys),
        "worker_fallback_evidence_stage_keys": worker_fallback_evidence_keys,
        "production_blocker_count": len(pending_keys),
        "missing_evidence": sorted({item for row in rows for item in _as_list(row.get("missing_evidence"))}),
        "not_allowed_next_steps": [
            "treat_stage_scope_manifest_as_worker_execution",
            "treat_stage_scope_manifest_as_provider_parity_acceptance",
            "treat_stage_scope_manifest_as_browser_or_ci_promotion",
            "retire_legacy_radar_from_stage_scope_manifest",
            "call_provider_model_or_github_from_get_cache_or_render",
            "mark_candidate_as_buy_instruction",
        ],
        "note": "This is a local pending production-stage manifest. It does not run scans, create worker tasks, call providers/models, promote browser artifacts, retire legacy radar, or complete production replacement.",
    }
    return manifest, rows


def _attach_candidate_radar_production_stage_scope_manifest(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    manifest, rows = _candidate_radar_production_stage_scope_manifest(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_production_stage_scope_count"] = manifest["row_count"]
    counts["candidate_radar_production_stage_scope_pending_count"] = manifest["pending_stage_count"]
    counts["candidate_radar_production_stage_scope_direct_evidence_count"] = manifest[
        "direct_evidence_stage_count"
    ]
    counts["candidate_radar_production_stage_scope_local_evidence_count"] = manifest["local_evidence_stage_count"]
    counts["candidate_radar_production_stage_scope_worker_fallback_evidence_count"] = manifest[
        "worker_fallback_evidence_stage_count"
    ]
    counts["candidate_radar_production_stage_scope_production_blocker_count"] = manifest["production_blocker_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_production_stage_scope_manifest_is_local"] = True
    policy["candidate_radar_production_stage_scope_manifest_is_not_execution"] = True
    policy["candidate_radar_production_stage_scope_manifest_is_not_production_replacement"] = True
    policy["candidate_radar_production_stage_scope_requires_worker_provider_browser_ci_evidence"] = True
    ledger = [
        row
        for row in _as_list(view.get("call_ledger"))
        if _as_dict(row).get("api") != "local_candidate_radar_production_stage_scope_manifest"
    ]
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_stage_scope_manifest",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=manifest["status"],
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar production stage-scope manifest 只列出生产替代剩余阶段；不会运行 worker、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_production_stage_scope_manifest"] = manifest
    view["candidate_radar_production_stage_scope_rows"] = rows
    return view


def _candidate_radar_production_replacement_review_row(
    review_key: str,
    category: str,
    status: str,
    *,
    passed: bool,
    local_review_required: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_SCHEMA_VERSION,
        "review_key": review_key,
        "category": category,
        "status": status,
        "passed": bool(passed),
        "local_review_required": bool(local_review_required),
        "production_blocker": bool(production_blocker),
        "recommended_order": int(recommended_order),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_stage_direct_keys(packet: Mapping[str, Any]) -> set[str]:
    manifest = _as_dict(packet.get("candidate_radar_production_stage_scope_manifest"))
    return {str(item) for item in _as_list(manifest.get("direct_evidence_stage_keys")) if str(item)}


def _candidate_stage_direct_evidence_done(packet: Mapping[str, Any], evidence_key: str) -> bool:
    return evidence_key in _candidate_stage_direct_keys(packet)


def _candidate_radar_production_replacement_review(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _as_dict(payload_safe)
    policy = _as_dict(packet.get("policy"))
    task_pipeline = _as_dict(packet.get("fast_scan_task_pipeline_contract"))
    legacy_receipt = _as_dict(packet.get("legacy_parity_acceptance_receipt"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    full_pool_receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    deep_scan_receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    provider_parity = _as_dict(packet.get("provider_parity_dry_run_receipt"))
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    worker_recipe = _as_dict(packet.get("candidate_radar_worker_execution_recipe"))
    worker_request = _as_dict(packet.get("candidate_radar_worker_execution_request_receipt"))
    full_pool_worker_fallback = _as_dict(packet.get("candidate_radar_full_pool_worker_fallback_receipt"))
    deep_scan_worker_fallback = _as_dict(packet.get("candidate_radar_deep_scan_worker_fallback_receipt"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    durable_recipe = _as_dict(packet.get("candidate_radar_durable_evidence_recipe"))
    stage_manifest = _as_dict(packet.get("candidate_radar_production_stage_scope_manifest"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))

    cache_render_safe = bool(
        packet.get("cache_only") is True
        and packet.get("read_only") is True
        and policy.get("does_not_scan_market") is True
        and policy.get("does_not_call_tushare") is True
        and policy.get("does_not_call_deepseek") is True
        and policy.get("does_not_call_github") is True
    )
    quick_pipeline_ready = task_pipeline.get("local_task_pipeline_ready") is True
    legacy_ready = legacy_receipt.get("local_acceptance_receipt_ready") is True
    no_loss_ready = no_loss.get("local_no_feature_loss_contract_ready") is True
    result_delta_ready = result_delta.get("local_result_delta_clarity_ready") is True
    local_full_pool_visible = (
        full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
    )
    local_deep_review_visible = (
        deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
    )
    provider_ticket_visible = bool(provider_parity.get("acceptance_scope_hash_short"))
    quant_request_visible = quant_request.get("local_execution_request_ready") is True
    worker_recipe_ready = worker_recipe.get("local_worker_execution_recipe_ready") is True
    worker_request_ready = worker_request.get("local_execution_request_ready") is True
    full_pool_worker_fallback_ready = full_pool_worker_fallback.get("local_worker_fallback_full_pool_done") is True
    deep_scan_worker_fallback_ready = deep_scan_worker_fallback.get("local_worker_fallback_deep_scan_done") is True
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    durable_recipe_ready = durable_recipe.get("local_recipe_ready") is True
    stage_manifest_ready = stage_manifest.get("local_manifest_ready") is True
    worker_full_pool_execution_done = _candidate_stage_direct_evidence_done(packet, "worker_full_pool_execution")
    worker_deep_scan_execution_done = _candidate_stage_direct_evidence_done(packet, "worker_deep_scan_execution")
    provider_backed_acceptance_done = bool(
        _candidate_stage_direct_evidence_done(packet, "provider_parity_acceptance")
        or durable_recipe.get("provider_call_ledger_evidence_done") is True
        or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
    )
    browser_visual_performance_promoted = _candidate_stage_direct_evidence_done(
        packet, "browser_visual_performance_promotion"
    )
    direct_worker_provider_browser_evidence_done = bool(
        worker_full_pool_execution_done
        and worker_deep_scan_execution_done
        and provider_backed_acceptance_done
        and browser_visual_performance_promoted
    )
    safety_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("external_calls_triggered") is not True
        and packet.get("tushare_called") is not True
        and packet.get("deepseek_called") is not True
        and packet.get("github_called") is not True
        and packet.get("contains_secret") is not True
    )

    rows = [
        _candidate_radar_production_replacement_review_row(
            "explicit_post_review_task",
            "review_gate",
            "passed_button_gated_review" if explicit_review else "pending_explicit_review",
            passed=explicit_review,
            local_review_required=True,
            production_blocker=False,
            evidence=f"route={CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_ROUTE}; task_id={task_id or '--'}",
            next_action="Run this review from an explicit button/POST task before judging Candidate Radar replacement readiness.",
            recommended_order=1,
        ),
        _candidate_radar_production_replacement_review_row(
            "cache_render_readonly_boundary",
            "local_surface",
            "passed_no_scan_on_render" if cache_render_safe else "blocked_render_boundary",
            passed=cache_render_safe,
            local_review_required=True,
            production_blocker=not cache_render_safe,
            evidence=f"cache_only={packet.get('cache_only')}; read_only={packet.get('read_only')}; does_not_scan_market={policy.get('does_not_scan_market')}",
            next_action="Keep GET cache and React render read-only and scan-silent.",
            recommended_order=2,
        ),
        _candidate_radar_production_replacement_review_row(
            "quick_scan_task_pipeline_visible",
            "local_surface",
            "passed_task_pipeline_visible" if quick_pipeline_ready else "blocked_task_pipeline",
            passed=quick_pipeline_ready,
            local_review_required=True,
            production_blocker=not quick_pipeline_ready,
            evidence=f"status={task_pipeline.get('status')}; blockers={task_pipeline.get('local_blocker_count')}",
            next_action="Keep quick/watchlist/custom scan behind explicit POST task/status flow.",
            recommended_order=3,
        ),
        _candidate_radar_production_replacement_review_row(
            "no_feature_loss_surface_visible",
            "local_surface",
            "passed_no_feature_loss_visible" if no_loss_ready else "blocked_no_feature_loss_surface",
            passed=no_loss_ready,
            local_review_required=True,
            production_blocker=not no_loss_ready,
            evidence=f"status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            next_action="Keep no-feature-loss gaps visible before retiring legacy radar.",
            recommended_order=4,
        ),
        _candidate_radar_production_replacement_review_row(
            "legacy_parity_receipt_visible",
            "local_surface",
            "passed_legacy_parity_visible" if legacy_ready else "blocked_legacy_parity_receipt",
            passed=legacy_ready,
            local_review_required=True,
            production_blocker=not legacy_ready,
            evidence=f"status={legacy_receipt.get('status')}; production_blockers={legacy_receipt.get('production_blocker_count')}",
            next_action="Do not treat gap_reported legacy rows as no-feature-loss completion.",
            recommended_order=5,
        ),
        _candidate_radar_production_replacement_review_row(
            "local_full_pool_receipt_visible",
            "local_surface",
            "passed_local_full_pool_receipt" if local_full_pool_visible else "pending_local_full_pool_receipt",
            passed=local_full_pool_visible,
            local_review_required=False,
            production_blocker=False,
            evidence=f"status={full_pool_receipt.get('status')}; production_full_pool_scan_done={full_pool_receipt.get('production_full_pool_scan_done')}",
            next_action="Keep local full-pool receipt separate from worker/provider-backed full-pool acceptance.",
            recommended_order=6,
        ),
        _candidate_radar_production_replacement_review_row(
            "local_deep_scan_review_visible",
            "local_surface",
            "passed_local_deep_review" if local_deep_review_visible else "pending_local_deep_review",
            passed=local_deep_review_visible,
            local_review_required=False,
            production_blocker=False,
            evidence=f"status={deep_scan_receipt.get('status')}; deep_scan_done={deep_scan_receipt.get('deep_scan_done')}",
            next_action="Keep local deep review separate from real DeepSeek/provider-backed deep scan.",
            recommended_order=7,
        ),
        _candidate_radar_production_replacement_review_row(
            "result_delta_clarity_visible",
            "local_surface",
            "passed_result_delta_visible" if result_delta_ready else "pending_result_delta_clarity",
            passed=result_delta_ready,
            local_review_required=False,
            production_blocker=False,
            evidence=f"status={result_delta.get('status')}; previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}",
            next_action="Use result deltas for clarity, not as browser visual QA replacement.",
            recommended_order=8,
        ),
        _candidate_radar_production_replacement_review_row(
            "provider_parity_scope_ticket_visible",
            "acceptance_ticket",
            "scope_ticket_visible" if provider_ticket_visible else "pending_provider_parity_dry_run",
            passed=provider_ticket_visible,
            local_review_required=False,
            production_blocker=not provider_ticket_visible,
            evidence=f"status={provider_parity.get('status')}; scope={provider_parity.get('acceptance_scope_hash_short') or 'missing'}",
            next_action="Run a user-approved provider parity dry-run before any real provider-backed parity task.",
            recommended_order=9,
        ),
        _candidate_radar_production_replacement_review_row(
            "worker_execution_request_visible",
            "acceptance_ticket",
            "worker_request_visible" if worker_request_ready else "pending_worker_execution_request",
            passed=worker_request_ready,
            local_review_required=False,
            production_blocker=not worker_request_ready,
            evidence=f"recipe_ready={worker_recipe_ready}; request_status={worker_request.get('status')}; scope_match={worker_request.get('requested_worker_execution_scope_hash_matches_latest')}",
            next_action="Bind worker full-pool/deep-scan execution to the current worker recipe hash before future execution.",
            recommended_order=10,
        ),
        _candidate_radar_production_replacement_review_row(
            "full_pool_worker_fallback_visible",
            "local_surface",
            "local_worker_fallback_visible" if full_pool_worker_fallback_ready else "pending_full_pool_worker_fallback",
            passed=full_pool_worker_fallback_ready,
            local_review_required=False,
            production_blocker=False,
            evidence=(
                f"status={full_pool_worker_fallback.get('status')}; "
                f"worker_runtime_pending={full_pool_worker_fallback.get('ready_for_worker_runtime_promotion') is False}"
            ),
            next_action="Use local worker fallback as route-shape evidence only; keep real Celery/Redis worker execution pending.",
            recommended_order=11,
        ),
        _candidate_radar_production_replacement_review_row(
            "deep_scan_worker_fallback_visible",
            "local_surface",
            "local_worker_fallback_visible" if deep_scan_worker_fallback_ready else "pending_deep_scan_worker_fallback",
            passed=deep_scan_worker_fallback_ready,
            local_review_required=False,
            production_blocker=False,
            evidence=(
                f"status={deep_scan_worker_fallback.get('status')}; "
                f"model_execution_pending={deep_scan_worker_fallback.get('model_execution_implemented') is False}"
            ),
            next_action="Use local deep-scan worker fallback as route-shape evidence only; keep real worker/model execution pending.",
            recommended_order=12,
        ),
        _candidate_radar_production_replacement_review_row(
            "quant_projection_execution_request_visible",
            "acceptance_ticket",
            "quant_request_visible" if quant_request_visible else "pending_quant_projection_execution_request",
            passed=quant_request_visible,
            local_review_required=False,
            production_blocker=not quant_request_visible,
            evidence=f"status={quant_request.get('status')}; scope_match={quant_request.get('requested_acceptance_scope_hash_matches_latest')}",
            next_action="Bind searched-symbol provider/model execution to a prior dry-run scope before future Tushare/DeepSeek execution.",
            recommended_order=13,
        ),
        _candidate_radar_production_replacement_review_row(
            "browser_qa_review_visible",
            "acceptance_ticket",
            "local_browser_review_ready" if browser_review_ready else "pending_browser_qa_review",
            passed=browser_review_ready,
            local_review_required=False,
            production_blocker=not browser_review_ready,
            evidence=f"status={browser_review.get('status')}; local_browser_qa_review_ready={browser_review_ready}",
            next_action="Attach browser visual/performance review evidence for #candidates before production replacement.",
            recommended_order=14,
        ),
        _candidate_radar_production_replacement_review_row(
            "durable_evidence_recipe_visible",
            "acceptance_ticket",
            "durable_recipe_visible" if durable_recipe_ready else "pending_durable_recipe",
            passed=durable_recipe_ready,
            local_review_required=True,
            production_blocker=not durable_recipe_ready,
            evidence=f"status={durable_recipe.get('status')}; blockers={durable_recipe.get('durable_evidence_blocker_count')}",
            next_action="Use durable evidence recipe as the checklist, not as production completion.",
            recommended_order=15,
        ),
        _candidate_radar_production_replacement_review_row(
            "production_stage_scope_manifest_visible",
            "acceptance_ticket",
            "stage_manifest_visible" if stage_manifest_ready else "pending_stage_manifest",
            passed=stage_manifest_ready,
            local_review_required=True,
            production_blocker=not stage_manifest_ready,
            evidence=f"status={stage_manifest.get('status')}; pending={stage_manifest.get('pending_stage_count')}",
            next_action="Keep stage-scope pending until direct worker/provider/browser/model evidence exists.",
            recommended_order=16,
        ),
        _candidate_radar_production_replacement_review_row(
            "direct_worker_provider_browser_evidence_required",
            "production_evidence",
            "direct_evidence_observed" if direct_worker_provider_browser_evidence_done else "pending_direct_evidence",
            passed=direct_worker_provider_browser_evidence_done,
            local_review_required=False,
            production_blocker=not direct_worker_provider_browser_evidence_done,
            evidence=(
                f"worker_full_pool_execution_done={worker_full_pool_execution_done}; "
                f"worker_deep_scan_execution_done={worker_deep_scan_execution_done}; "
                f"provider_backed_acceptance_done={provider_backed_acceptance_done}; "
                f"browser_visual_performance_promoted={browser_visual_performance_promoted}"
            ),
            next_action="Collect real worker full-pool/deep-scan, provider call ledger, optional model ledger, and browser performance promotion evidence.",
            recommended_order=17,
        ),
        _candidate_radar_production_replacement_review_row(
            "legacy_retirement_stays_blocked",
            "production_boundary",
            "blocked_legacy_retirement",
            passed=False,
            local_review_required=False,
            production_blocker=True,
            evidence=f"promotion_ready={promotion.get('promotion_ready')}; legacy_retirement_ready={stage_manifest.get('legacy_retirement_ready')}",
            next_action="Keep Streamlit/legacy radar fallback until production promotion review clears.",
            recommended_order=18,
        ),
        _candidate_radar_production_replacement_review_row(
            "no_trade_action_secret_boundary",
            "safety",
            "passed_research_only_secret_safe" if safety_ready else "blocked_safety_boundary",
            passed=safety_ready,
            local_review_required=True,
            production_blocker=not safety_ready,
            evidence="Candidate Radar review does not call external providers/models, expose secrets, execute trades, or mutate strategy action.",
            next_action="Preserve research-only boundaries in every future radar execution task.",
            recommended_order=19,
        ),
    ]

    local_blockers = [row["review_key"] for row in rows if row["local_review_required"] and not row["passed"]]
    production_blockers = [row["review_key"] for row in rows if row["production_blocker"] and not row["passed"]]
    local_ready = explicit_review and not local_blockers
    scope_input = {
        "schema_version": CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_SCHEMA_VERSION,
        "task_pipeline_status": task_pipeline.get("status"),
        "legacy_status": legacy_receipt.get("status"),
        "no_loss_status": no_loss.get("status"),
        "provider_scope": provider_parity.get("acceptance_scope_hash_short"),
        "worker_scope": worker_request.get("worker_execution_scope_hash_short"),
        "quant_scope": quant_request.get("acceptance_scope_hash_short"),
        "browser_status": browser_review.get("status"),
        "production_blockers": production_blockers,
    }
    serialized = json.dumps(_safe_value(scope_input), ensure_ascii=False, sort_keys=True, default=str)
    review_scope_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    reviewer = _safe_text(payload.get("reviewer") or payload.get("requested_by") or "local_operator", limit=80)
    receipt = {
        "schema_version": CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_SCHEMA_VERSION,
        "status": (
            "candidate_radar_production_replacement_review_ready_production_blocked"
            if local_ready
            else "candidate_radar_production_replacement_review_blocked_local_review"
        ),
        "scope": "button_gated_local_candidate_radar_production_replacement_review_no_external_call",
        "ltg": "LTG-13",
        "route": CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_ROUTE,
        "task_type": CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_TASK_TYPE,
        "explicit_review_task_done": bool(explicit_review),
        "task_id": task_id,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "local_review_ready": local_ready,
        "ready_for_production_replacement": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "fast_scan_ready": quick_pipeline_ready and no_loss_ready,
        "no_feature_loss_local_surface_ready": no_loss_ready,
        "legacy_parity_receipt_ready": legacy_ready,
        "local_full_pool_receipt_visible": local_full_pool_visible,
        "local_deep_scan_review_visible": local_deep_review_visible,
        "provider_parity_scope_ticket_visible": provider_ticket_visible,
        "worker_execution_request_visible": worker_request_ready,
        "full_pool_worker_fallback_visible": full_pool_worker_fallback_ready,
        "deep_scan_worker_fallback_visible": deep_scan_worker_fallback_ready,
        "quant_projection_execution_request_visible": quant_request_visible,
        "browser_qa_review_visible": browser_review_ready,
        "durable_evidence_recipe_visible": durable_recipe_ready,
        "stage_scope_manifest_visible": stage_manifest_ready,
        "worker_full_pool_execution_done": worker_full_pool_execution_done,
        "local_full_pool_worker_fallback_done": full_pool_worker_fallback_ready,
        "local_deep_scan_worker_fallback_done": deep_scan_worker_fallback_ready,
        "worker_deep_scan_execution_done": worker_deep_scan_execution_done,
        "provider_backed_acceptance_done": provider_backed_acceptance_done,
        "deepseek_model_ledger_complete": False,
        "browser_visual_performance_promoted": browser_visual_performance_promoted,
        "durable_evidence_complete": False,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "review_scope_hash": review_scope_hash,
        "review_scope_hash_short": review_scope_hash[:16],
        "review_scope_hash_algorithm": "sha256",
        "review_scope_hash_input_includes_secret": False,
        "required_before_production_replacement": [
            "worker-backed full-pool execution evidence",
            "worker-backed deep-scan execution evidence",
            "provider-backed radar parity call ledger",
            "searched-symbol Tushare/DeepSeek ledger when enabled",
            "browser visual/performance promotion evidence",
            "legacy retirement review",
            "production promotion and redaction review",
        ],
        "not_allowed_next_steps": [
            "treat production replacement review as production completion",
            "retire legacy radar fallback from local review",
            "treat local full-pool receipt as worker full-pool execution",
            "treat local deep review as provider/model deep scan",
            "call Tushare/DeepSeek/GitHub from GET cache or render",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "allowed_next_step": "run_user_approved_worker_provider_browser_acceptance_tasks",
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This is a button-gated local production-replacement review receipt for LTG-13. It organizes direct evidence still needed for Candidate Radar replacement, but it does not run scans, start workers, call Tushare/DeepSeek/GitHub, retire legacy radar, or complete production replacement.",
    }
    return receipt, rows


def _attach_candidate_radar_production_replacement_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    persisted_receipt = _as_dict(view.get("candidate_radar_production_replacement_review_receipt"))
    explicit_review = persisted_receipt.get("explicit_review_task_done") is True
    receipt, rows = _candidate_radar_production_replacement_review(
        view,
        payload_safe={},
        explicit_review=explicit_review,
        task_id=str(persisted_receipt.get("task_id") or view.get("task_id") or "") if explicit_review else None,
        reviewed_at=str(
            persisted_receipt.get("reviewed_at")
            or view.get("candidate_radar_production_replacement_review_completed_at")
            or ""
        )
        if explicit_review
        else None,
    )
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_production_replacement_review_row_count"] = receipt["row_count"]
    counts["candidate_radar_production_replacement_review_local_blocker_count"] = receipt["local_blocker_count"]
    counts["candidate_radar_production_replacement_review_production_blocker_count"] = receipt[
        "production_blocker_count"
    ]
    counts["candidate_radar_production_replacement_review_ready"] = receipt["local_review_ready"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_production_replacement_review_is_button_gated"] = explicit_review
    policy["candidate_radar_production_replacement_review_is_local"] = True
    policy["candidate_radar_production_replacement_review_calls_provider_or_model"] = False
    policy["candidate_radar_production_replacement_review_is_not_production_replacement"] = True
    policy["candidate_radar_production_replacement_review_requires_direct_worker_provider_browser_evidence"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_replacement_review_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=receipt["status"],
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar production replacement review 只审查本地迁移证据和缺口；不会运行扫描、启动 worker、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_production_replacement_review_receipt"] = receipt
    view["candidate_radar_production_replacement_review_rows"] = rows
    return view


def _candidate_radar_production_promotion_dry_run_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "recommended_order": int(recommended_order),
        "evidence": evidence,
        "next_action": next_action,
        "local_dry_run_only": True,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_production_promotion_dry_run_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_dry_run: bool = False,
    task_id: str | None = None,
    created_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _as_dict(payload_safe)
    operator_approved = _coerce_bool(
        payload.get("operator_approved")
        or payload.get("approved_by_user")
        or payload.get("user_approved")
        or payload.get("approved"),
        False,
    )
    production_review = _as_dict(packet.get("candidate_radar_production_replacement_review_receipt"))
    durable_recipe = _as_dict(packet.get("candidate_radar_durable_evidence_recipe"))
    stage_manifest = _as_dict(packet.get("candidate_radar_production_stage_scope_manifest"))
    requested_review_hash = _safe_text(
        payload.get("review_scope_hash")
        or payload.get("production_replacement_review_scope_hash")
        or payload.get("scope_hash")
        or "",
        limit=128,
    )
    expected_review_hash = _safe_text(production_review.get("review_scope_hash") or "", limit=128)
    scope_hash_matches = bool(
        requested_review_hash and expected_review_hash and requested_review_hash == expected_review_hash
    )
    production_review_ready = production_review.get("local_review_ready") is True
    durable_recipe_visible = durable_recipe.get("local_recipe_ready") is True
    stage_manifest_visible = stage_manifest.get("local_manifest_ready") is True
    worker_full_pool_done = (
        production_review.get("worker_full_pool_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_full_pool_execution")
    )
    worker_deep_scan_done = (
        production_review.get("worker_deep_scan_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_deep_scan_execution")
    )
    provider_backed_done = (
        production_review.get("provider_backed_acceptance_done") is True
        or _candidate_stage_direct_evidence_done(packet, "provider_parity_acceptance")
    )
    provider_call_ledger_evidence_done = bool(
        durable_recipe.get("provider_call_ledger_evidence_done") is True
        or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
        or provider_backed_done
    )
    model_ledger_done = production_review.get("deepseek_model_ledger_complete") is True
    browser_promoted = (
        production_review.get("browser_visual_performance_promoted") is True
        or _candidate_stage_direct_evidence_done(packet, "browser_visual_performance_promotion")
    )
    durable_evidence_complete = production_review.get("durable_evidence_complete") is True
    legacy_retirement_ready = production_review.get("legacy_retirement_ready") is True
    safety_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("external_calls_triggered") is not True
        and packet.get("tushare_called") is not True
        and packet.get("deepseek_called") is not True
        and packet.get("github_called") is not True
        and packet.get("contains_secret") is not True
    )
    rows = [
        _candidate_radar_production_promotion_dry_run_row(
            "explicit_promotion_dry_run_task",
            "passed_explicit_post" if explicit_dry_run else "blocked_missing_explicit_post",
            passed=explicit_dry_run,
            local_blocker=not explicit_dry_run,
            production_blocker=False,
            evidence=f"route={CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_ROUTE}; task_id={task_id or '--'}",
            next_action="Use only the explicit POST route to create a production promotion dry-run ticket.",
            recommended_order=1,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_dry_run and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before binding promotion scope.",
            recommended_order=2,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "production_replacement_review_scope_bound",
            "passed_review_scope_bound" if scope_hash_matches else "blocked_review_scope_hash_missing_or_mismatch",
            passed=scope_hash_matches,
            local_blocker=explicit_dry_run and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_review_hash[:16] if requested_review_hash else 'missing'}; "
                f"expected={expected_review_hash[:16] if expected_review_hash else 'missing'}"
            ),
            next_action="Bind this dry-run to the latest production replacement review scope hash.",
            recommended_order=3,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "production_replacement_review_ready",
            "passed_review_ready" if production_review_ready else "blocked_replacement_review_missing",
            passed=production_review_ready,
            local_blocker=not production_review_ready,
            production_blocker=False,
            evidence=f"status={production_review.get('status')}; local_review_ready={production_review_ready}",
            next_action="Run the production replacement review before creating a promotion dry-run ticket.",
            recommended_order=4,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "durable_evidence_recipe_visible",
            "passed_durable_recipe_visible" if durable_recipe_visible else "blocked_durable_recipe_missing",
            passed=durable_recipe_visible,
            local_blocker=not durable_recipe_visible,
            production_blocker=False,
            evidence=f"status={durable_recipe.get('status')}; local_recipe_ready={durable_recipe_visible}",
            next_action="Keep the durable evidence checklist visible before any promotion decision.",
            recommended_order=5,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "production_stage_scope_manifest_visible",
            "passed_stage_scope_visible" if stage_manifest_visible else "blocked_stage_scope_missing",
            passed=stage_manifest_visible,
            local_blocker=not stage_manifest_visible,
            production_blocker=False,
            evidence=f"status={stage_manifest.get('status')}; pending={stage_manifest.get('pending_stage_count')}",
            next_action="Keep the LTG-13 production stage manifest visible during promotion review.",
            recommended_order=6,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "worker_full_pool_execution_evidence_required",
            "completed" if worker_full_pool_done else "pending_worker_full_pool_execution",
            passed=worker_full_pool_done,
            local_blocker=False,
            production_blocker=not worker_full_pool_done,
            evidence=f"worker_full_pool_execution_done={worker_full_pool_done}",
            next_action="Attach real worker-backed full-pool execution evidence before promotion.",
            recommended_order=7,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "worker_deep_scan_execution_evidence_required",
            "completed" if worker_deep_scan_done else "pending_worker_deep_scan_execution",
            passed=worker_deep_scan_done,
            local_blocker=False,
            production_blocker=not worker_deep_scan_done,
            evidence=f"worker_deep_scan_execution_done={worker_deep_scan_done}",
            next_action="Attach real worker-backed deep-scan execution evidence before promotion.",
            recommended_order=8,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "provider_backed_parity_call_ledger_required",
            "provider_call_ledger_observed"
            if provider_call_ledger_evidence_done
            else "pending_provider_backed_parity",
            passed=provider_call_ledger_evidence_done,
            local_blocker=False,
            production_blocker=not provider_call_ledger_evidence_done,
            evidence=(
                f"provider_backed_acceptance_done={provider_backed_done}; "
                f"provider_call_ledger_evidence_done={provider_call_ledger_evidence_done}"
            ),
            next_action="Attach real provider call ledger and parity evidence before promotion.",
            recommended_order=9,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "deepseek_model_ledger_if_enabled_required",
            "completed" if model_ledger_done else "pending_model_ledger",
            passed=model_ledger_done,
            local_blocker=False,
            production_blocker=True,
            evidence=f"deepseek_model_ledger_complete={model_ledger_done}",
            next_action="If DeepSeek is enabled for radar deep research, attach model ledger, sanitizer, cost, hash, and parse-failed evidence.",
            recommended_order=10,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "browser_visual_performance_promotion_required",
            "promoted" if browser_promoted else "pending_browser_visual_performance_promotion",
            passed=browser_promoted,
            local_blocker=False,
            production_blocker=not browser_promoted,
            evidence=f"browser_visual_performance_promoted={browser_promoted}",
            next_action="Promote durable browser visual/performance evidence before production replacement.",
            recommended_order=11,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "legacy_retirement_review_required",
            "ready_for_legacy_retirement" if legacy_retirement_ready else "pending_legacy_retirement_review",
            passed=legacy_retirement_ready,
            local_blocker=False,
            production_blocker=not legacy_retirement_ready,
            evidence=f"legacy_retirement_ready={legacy_retirement_ready}",
            next_action="Keep Streamlit legacy radar fallback until replacement evidence and retirement review pass.",
            recommended_order=12,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "durable_ci_or_release_evidence_required",
            "complete" if durable_evidence_complete else "pending_durable_release_evidence",
            passed=durable_evidence_complete,
            local_blocker=False,
            production_blocker=not durable_evidence_complete,
            evidence=f"durable_evidence_complete={durable_evidence_complete}",
            next_action="Attach durable local/CI/release evidence before marking production replacement complete.",
            recommended_order=13,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "production_completion_stays_blocked",
            "blocked_until_direct_evidence",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="The dry-run is a local scope ticket and never marks production_radar_replacement_complete.",
            next_action="Run real worker/provider/model/browser acceptance and a separate promotion review before completion.",
            recommended_order=14,
        ),
        _candidate_radar_production_promotion_dry_run_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects" if safety_ready else "blocked_safety_boundary",
            passed=safety_ready,
            local_blocker=not safety_ready,
            production_blocker=not safety_ready,
            evidence="No provider/model/GitHub calls, no trades, no action mutation, and no secret persistence.",
            next_action="Preserve this boundary when replacing dry-run with real promotion evidence.",
            recommended_order=15,
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    ready_for_local_review = explicit_dry_run and operator_approved and not local_blockers
    if not explicit_dry_run:
        status = "candidate_radar_production_promotion_dry_run_missing"
        allowed_next_step = "run_button_gated_candidate_radar_production_promotion_dry_run"
    elif not operator_approved:
        status = "candidate_radar_production_promotion_dry_run_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif not production_review_ready:
        status = "candidate_radar_production_promotion_dry_run_blocked_replacement_review_required"
        allowed_next_step = "run_candidate_radar_production_replacement_review"
    elif not scope_hash_matches:
        status = "candidate_radar_production_promotion_dry_run_blocked_scope_hash_mismatch"
        allowed_next_step = "rerun_against_latest_production_replacement_review_scope_hash"
    elif not (durable_recipe_visible and stage_manifest_visible and safety_ready):
        status = "candidate_radar_production_promotion_dry_run_blocked_local_surface"
        allowed_next_step = "restore_durable_recipe_stage_manifest_and_safety_boundary"
    else:
        status = "candidate_radar_production_promotion_dry_run_ready_production_still_blocked"
        allowed_next_step = "collect_direct_worker_provider_model_browser_legacy_evidence"
    promotion_scope_input = {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION,
        "review_scope_hash": expected_review_hash,
        "production_blockers": production_blockers,
        "worker_full_pool_done": worker_full_pool_done,
        "worker_deep_scan_done": worker_deep_scan_done,
        "provider_backed_done": provider_backed_done,
        "model_ledger_done": model_ledger_done,
        "browser_promoted": browser_promoted,
        "legacy_retirement_ready": legacy_retirement_ready,
        "durable_evidence_complete": durable_evidence_complete,
    }
    promotion_scope_hash = hashlib.sha256(
        json.dumps(_safe_value(promotion_scope_input), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    receipt = {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_candidate_radar_production_promotion_dry_run_no_external_call",
        "ltg": "LTG-13",
        "route": CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_ROUTE,
        "task_type": CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_TASK_TYPE,
        "task_id": task_id or "",
        "created_at": created_at,
        "explicit_promotion_dry_run_task_done": explicit_dry_run,
        "operator_approved": operator_approved,
        "button_gated": True,
        "local_dry_run_only": True,
        "ready_for_local_promotion_review": ready_for_local_review,
        "ready_to_mark_production_radar_replacement_complete": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "production_replacement_review_ready": production_review_ready,
        "production_replacement_review_scope_hash": expected_review_hash,
        "production_replacement_review_scope_hash_short": expected_review_hash[:16] if expected_review_hash else "",
        "requested_review_scope_hash": requested_review_hash,
        "requested_review_scope_hash_matches_latest": scope_hash_matches,
        "promotion_scope_hash": promotion_scope_hash,
        "promotion_scope_hash_short": promotion_scope_hash[:16],
        "promotion_scope_hash_algorithm": "sha256",
        "promotion_scope_hash_input_includes_secret": False,
        "worker_full_pool_execution_done": worker_full_pool_done,
        "worker_deep_scan_execution_done": worker_deep_scan_done,
        "provider_backed_acceptance_done": provider_backed_done,
        "provider_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "deepseek_model_ledger_complete": model_ledger_done,
        "browser_visual_performance_promoted": browser_promoted,
        "durable_evidence_complete": durable_evidence_complete,
        "durable_ci_or_release_evidence_required": True,
        "durable_ci_or_release_evidence_complete": False,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "row_count": len(rows),
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "treat promotion dry-run as production radar replacement",
            "treat local review as direct worker/provider/model/browser evidence",
            "retire legacy radar fallback from promotion dry-run",
            "call Tushare/DeepSeek/GitHub from GET cache or React render",
            "start Redis/Celery worker from this dry-run",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This dry-run binds the local production replacement review scope for LTG-13 promotion review. It does not execute worker/provider/model/browser work, retire legacy radar, or mark production replacement complete.",
    }
    return receipt, rows


def _attach_candidate_radar_production_promotion_dry_run(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_production_promotion_dry_run_receipt"))
    if existing.get("schema_version") == CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("candidate_radar_production_promotion_dry_run_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
    else:
        receipt, rows = _candidate_radar_production_promotion_dry_run_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_production_promotion_dry_run_row_count"] = len(rows)
    counts["candidate_radar_production_promotion_dry_run_local_blocker_count"] = receipt.get(
        "local_blocker_count", 0
    )
    counts["candidate_radar_production_promotion_dry_run_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_production_promotion_dry_run_ready"] = (
        receipt.get("ready_for_local_promotion_review") is True
    )
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_production_promotion_dry_run_is_button_gated"] = True
    policy["candidate_radar_production_promotion_dry_run_is_local"] = True
    policy["candidate_radar_production_promotion_dry_run_does_not_start_worker"] = True
    policy["candidate_radar_production_promotion_dry_run_calls_no_provider_model_github"] = True
    policy["candidate_radar_production_promotion_dry_run_is_not_production_replacement"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_promotion_dry_run_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_production_promotion_dry_run_missing"),
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar production promotion dry-run 只绑定本地 production review scope；不会运行 worker、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_production_promotion_dry_run_receipt"] = receipt
    view["candidate_radar_production_promotion_dry_run_rows"] = rows
    return view


def _candidate_radar_production_promotion_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "recommended_order": int(recommended_order),
        "evidence": evidence,
        "next_action": next_action,
        "local_review_only": True,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_production_promotion_review_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _as_dict(payload_safe)
    operator_approved = _coerce_bool(
        payload.get("operator_approved")
        or payload.get("approved_by_user")
        or payload.get("user_approved")
        or payload.get("approved"),
        False,
    )
    promotion_dry_run = _as_dict(packet.get("candidate_radar_production_promotion_dry_run_receipt"))
    legacy_review = _as_dict(packet.get("candidate_radar_legacy_retirement_review_receipt"))
    durable_recipe = _as_dict(packet.get("candidate_radar_durable_evidence_recipe"))
    stage_manifest = _as_dict(packet.get("candidate_radar_production_stage_scope_manifest"))
    production_review = _as_dict(packet.get("candidate_radar_production_replacement_review_receipt"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    browser_evidence = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    requested_promotion_hash = _safe_text(
        payload.get("promotion_scope_hash")
        or payload.get("production_promotion_scope_hash")
        or payload.get("scope_hash")
        or "",
        limit=128,
    )
    expected_promotion_hash = _safe_text(promotion_dry_run.get("promotion_scope_hash") or "", limit=128)
    scope_hash_matches = bool(
        requested_promotion_hash and expected_promotion_hash and requested_promotion_hash == expected_promotion_hash
    )
    promotion_dry_run_visible = promotion_dry_run.get("ready_for_local_promotion_review") is True
    legacy_review_visible = legacy_review.get("local_review_ready") is True
    durable_recipe_visible = durable_recipe.get("local_recipe_ready") is True
    stage_manifest_visible = stage_manifest.get("local_manifest_ready") is True
    production_review_ready = production_review.get("local_review_ready") is True
    worker_full_pool_done = (
        production_review.get("worker_full_pool_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_full_pool_execution")
    )
    worker_deep_scan_done = (
        production_review.get("worker_deep_scan_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_deep_scan_execution")
    )
    provider_backed_done = (
        production_review.get("provider_backed_acceptance_done") is True
        or _candidate_stage_direct_evidence_done(packet, "provider_parity_acceptance")
    )
    provider_call_ledger_evidence_done = bool(
        durable_recipe.get("provider_call_ledger_evidence_done") is True
        or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
        or provider_backed_done
    )
    model_ledger_done = production_review.get("deepseek_model_ledger_complete") is True
    production_review_browser_promoted = (
        production_review.get("browser_visual_performance_promoted") is True
        or _candidate_stage_direct_evidence_done(packet, "browser_visual_performance_promotion")
    )
    durable_evidence_complete = production_review.get("durable_evidence_complete") is True
    legacy_retirement_ready = legacy_review.get("legacy_retirement_ready") is True
    safety_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("external_calls_triggered") is not True
        and packet.get("tushare_called") is not True
        and packet.get("deepseek_called") is not True
        and packet.get("github_called") is not True
        and packet.get("contains_secret") is not True
    )
    browser_review_ready = bool(
        browser_review.get("status") == "candidate_browser_qa_review_ready_local_artifact"
        and browser_review.get("local_browser_qa_review_ready") is True
        and browser_review.get("local_browser_qa_evidence_found") is True
        and browser_review.get("candidate_visual_qa_evidence_passed") is True
        and browser_review.get("candidate_browser_performance_evidence_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
        and (browser_review.get("blocking_review_count") or 0) == 0
        and (browser_review.get("review_required_count") or 0) == 0
        and browser_review.get("production_radar_replacement_complete") is False
        and browser_review.get("legacy_retirement_ready") is False
        and browser_review.get("external_calls_triggered") is not True
        and browser_review.get("tushare_called") is not True
        and browser_review.get("deepseek_called") is not True
        and browser_review.get("github_called") is not True
        and browser_review.get("does_not_execute_trades") is True
        and browser_review.get("does_not_modify_strategy_action") is True
        and browser_review.get("candidate_is_not_buy_instruction") is True
    )
    browser_evidence_ready = bool(
        browser_evidence.get("status") == "candidate_browser_qa_evidence_passed_local_artifact"
        and browser_evidence.get("candidate_browser_qa_evidence_ready") is True
        and browser_evidence.get("local_browser_qa_evidence_found") is True
        and browser_evidence.get("candidate_visual_qa_evidence_passed") is True
        and browser_evidence.get("candidate_browser_performance_evidence_passed") is True
        and browser_evidence.get("motion_viewport_coverage_complete") is True
        and (browser_evidence.get("review_required_count") or 0) == 0
        and browser_evidence.get("production_radar_replacement_complete") is False
        and browser_evidence.get("legacy_retirement_ready") is False
        and browser_evidence.get("external_calls_triggered") is not True
        and browser_evidence.get("tushare_called") is not True
        and browser_evidence.get("deepseek_called") is not True
        and browser_evidence.get("github_called") is not True
        and browser_evidence.get("does_not_execute_trades") is True
        and browser_evidence.get("does_not_modify_strategy_action") is True
        and browser_evidence.get("candidate_is_not_buy_instruction") is True
    )
    browser_promotion_from_local_qa = bool(browser_review_ready and browser_evidence_ready and safety_ready)
    browser_promoted = production_review_browser_promoted or browser_promotion_from_local_qa
    rows = [
        _candidate_radar_production_promotion_review_row(
            "explicit_production_promotion_review_task",
            "passed_explicit_post" if explicit_review else "blocked_missing_explicit_post",
            passed=explicit_review,
            local_blocker=not explicit_review,
            production_blocker=False,
            evidence=f"route={CANDIDATE_PRODUCTION_PROMOTION_REVIEW_ROUTE}; task_id={task_id or '--'}",
            next_action="Run this review only from the explicit POST/button gate.",
            recommended_order=1,
        ),
        _candidate_radar_production_promotion_review_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_review and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before creating the promotion review receipt.",
            recommended_order=2,
        ),
        _candidate_radar_production_promotion_review_row(
            "production_promotion_dry_run_scope_bound",
            "passed_promotion_scope_bound" if scope_hash_matches else "blocked_promotion_scope_hash_missing_or_mismatch",
            passed=scope_hash_matches,
            local_blocker=explicit_review and not scope_hash_matches,
            production_blocker=False,
            evidence=(
                f"requested={requested_promotion_hash[:16] if requested_promotion_hash else 'missing'}; "
                f"expected={expected_promotion_hash[:16] if expected_promotion_hash else 'missing'}"
            ),
            next_action="Bind promotion review to the latest local promotion dry-run scope hash.",
            recommended_order=3,
        ),
        _candidate_radar_production_promotion_review_row(
            "production_replacement_review_visible",
            "passed_replacement_review_visible" if production_review_ready else "blocked_replacement_review_required",
            passed=production_review_ready,
            local_blocker=not production_review_ready,
            production_blocker=False,
            evidence=f"status={production_review.get('status')}; local_review_ready={production_review_ready}",
            next_action="Run Candidate Radar production replacement review before promotion review.",
            recommended_order=4,
        ),
        _candidate_radar_production_promotion_review_row(
            "production_promotion_dry_run_visible",
            "passed_promotion_dry_run_visible" if promotion_dry_run_visible else "blocked_promotion_dry_run_required",
            passed=promotion_dry_run_visible,
            local_blocker=not promotion_dry_run_visible,
            production_blocker=False,
            evidence=f"status={promotion_dry_run.get('status')}; ready={promotion_dry_run_visible}",
            next_action="Create the local promotion dry-run before promotion review.",
            recommended_order=5,
        ),
        _candidate_radar_production_promotion_review_row(
            "legacy_retirement_review_visible",
            "passed_legacy_review_visible" if legacy_review_visible else "blocked_legacy_retirement_review_required",
            passed=legacy_review_visible,
            local_blocker=not legacy_review_visible,
            production_blocker=False,
            evidence=f"status={legacy_review.get('status')}; local_review_ready={legacy_review_visible}",
            next_action="Run the local legacy retirement review before final promotion review.",
            recommended_order=6,
        ),
        _candidate_radar_production_promotion_review_row(
            "durable_evidence_recipe_visible",
            "passed_durable_recipe_visible" if durable_recipe_visible else "blocked_durable_recipe_required",
            passed=durable_recipe_visible,
            local_blocker=not durable_recipe_visible,
            production_blocker=False,
            evidence=f"status={durable_recipe.get('status')}; blockers={durable_recipe.get('durable_evidence_blocker_count')}",
            next_action="Keep the durable evidence checklist visible before promotion review.",
            recommended_order=7,
        ),
        _candidate_radar_production_promotion_review_row(
            "production_stage_manifest_visible",
            "passed_stage_manifest_visible" if stage_manifest_visible else "blocked_stage_manifest_required",
            passed=stage_manifest_visible,
            local_blocker=not stage_manifest_visible,
            production_blocker=False,
            evidence=f"status={stage_manifest.get('status')}; pending={stage_manifest.get('pending_stage_count')}",
            next_action="Keep the production stage manifest visible during promotion review.",
            recommended_order=8,
        ),
        _candidate_radar_production_promotion_review_row(
            "worker_full_pool_execution_evidence_required",
            "completed" if worker_full_pool_done else "pending_worker_full_pool_execution",
            passed=worker_full_pool_done,
            local_blocker=False,
            production_blocker=not worker_full_pool_done,
            evidence=f"worker_full_pool_execution_done={worker_full_pool_done}",
            next_action="Attach real worker-backed full-pool execution evidence before promotion.",
            recommended_order=9,
        ),
        _candidate_radar_production_promotion_review_row(
            "worker_deep_scan_execution_evidence_required",
            "completed" if worker_deep_scan_done else "pending_worker_deep_scan_execution",
            passed=worker_deep_scan_done,
            local_blocker=False,
            production_blocker=not worker_deep_scan_done,
            evidence=f"worker_deep_scan_execution_done={worker_deep_scan_done}",
            next_action="Attach real worker-backed deep-scan execution evidence before promotion.",
            recommended_order=10,
        ),
        _candidate_radar_production_promotion_review_row(
            "provider_backed_parity_call_ledger_required",
            "provider_call_ledger_observed"
            if provider_call_ledger_evidence_done
            else "pending_provider_call_ledger",
            passed=provider_call_ledger_evidence_done,
            local_blocker=False,
            production_blocker=not provider_call_ledger_evidence_done,
            evidence=(
                f"provider_backed_acceptance_done={provider_backed_done}; "
                f"provider_call_ledger_evidence_done={provider_call_ledger_evidence_done}"
            ),
            next_action="Attach provider-backed parity call ledger before promotion.",
            recommended_order=11,
        ),
        _candidate_radar_production_promotion_review_row(
            "deepseek_model_ledger_if_enabled_required",
            "completed" if model_ledger_done else "pending_model_ledger",
            passed=model_ledger_done,
            local_blocker=False,
            production_blocker=True,
            evidence=f"deepseek_model_ledger_complete={model_ledger_done}",
            next_action="If DeepSeek is enabled for radar, attach model ledger, sanitizer, parse-failed, and cost evidence.",
            recommended_order=12,
        ),
        _candidate_radar_production_promotion_review_row(
            "browser_visual_performance_promotion_required",
            "promoted_local_browser_qa_review"
            if browser_promotion_from_local_qa
            else ("promoted" if browser_promoted else "pending_browser_visual_performance_promotion"),
            passed=browser_promoted,
            local_blocker=False,
            production_blocker=not browser_promoted,
            evidence=(
                f"browser_visual_performance_promoted={browser_promoted}; "
                f"browser_review_status={browser_review.get('status') or 'missing'}; "
                f"browser_evidence_status={browser_evidence.get('status') or 'missing'}"
            ),
            next_action=(
                "Keep local browser QA promotion evidence attached; production replacement still requires "
                "worker/provider/model/release/legacy evidence."
                if browser_promoted
                else "Promote durable browser visual/performance evidence before production replacement."
            ),
            recommended_order=13,
        ),
        _candidate_radar_production_promotion_review_row(
            "durable_ci_or_release_evidence_required",
            "complete" if durable_evidence_complete else "pending_durable_release_evidence",
            passed=durable_evidence_complete,
            local_blocker=False,
            production_blocker=not durable_evidence_complete,
            evidence=f"durable_evidence_complete={durable_evidence_complete}",
            next_action="Attach durable local/CI/release evidence before marking production replacement complete.",
            recommended_order=14,
        ),
        _candidate_radar_production_promotion_review_row(
            "legacy_retirement_ready_required",
            "ready_for_legacy_retirement" if legacy_retirement_ready else "pending_legacy_retirement_ready",
            passed=legacy_retirement_ready,
            local_blocker=False,
            production_blocker=not legacy_retirement_ready,
            evidence=f"legacy_retirement_ready={legacy_retirement_ready}; legacy_review_visible={legacy_review_visible}",
            next_action="Keep Streamlit/legacy radar fallback until direct evidence supports retirement.",
            recommended_order=15,
        ),
        _candidate_radar_production_promotion_review_row(
            "production_completion_stays_blocked",
            "blocked_until_direct_evidence",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Production promotion review is local review evidence and never marks production_radar_replacement_complete.",
            next_action="Complete real worker/provider/model/browser/release evidence before production replacement.",
            recommended_order=16,
        ),
        _candidate_radar_production_promotion_review_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects" if safety_ready else "blocked_safety_boundary",
            passed=safety_ready,
            local_blocker=not safety_ready,
            production_blocker=not safety_ready,
            evidence="No provider/model/GitHub calls, no trades, no action mutation, and no secret persistence.",
            next_action="Preserve this boundary when replacing local review with real promotion evidence.",
            recommended_order=17,
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    local_ready = explicit_review and operator_approved and not local_blockers
    if not explicit_review:
        status = "candidate_radar_production_promotion_review_missing"
        allowed_next_step = "run_button_gated_candidate_radar_production_promotion_review"
    elif not operator_approved:
        status = "candidate_radar_production_promotion_review_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif local_blockers:
        status = "candidate_radar_production_promotion_review_blocked_local_review"
        allowed_next_step = "restore_required_local_promotion_and_legacy_review_receipts"
    else:
        status = "candidate_radar_production_promotion_review_ready_production_blocked"
        allowed_next_step = "collect_direct_worker_provider_model_browser_release_evidence"
    promotion_review_scope_input = {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "production_review_scope_hash": production_review.get("review_scope_hash"),
        "promotion_scope_hash": expected_promotion_hash,
        "legacy_retirement_scope_hash": legacy_review.get("retirement_scope_hash"),
        "production_blockers": production_blockers,
        "local_blockers": local_blockers,
        "production_radar_replacement_complete": False,
    }
    promotion_review_scope_hash = hashlib.sha256(
        json.dumps(_safe_value(promotion_review_scope_input), ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()
    reviewer = _safe_text(payload.get("reviewer") or payload.get("requested_by") or "local_operator", limit=80)
    receipt = {
        "schema_version": CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_candidate_radar_production_promotion_review_no_external_call",
        "ltg": "LTG-13",
        "route": CANDIDATE_PRODUCTION_PROMOTION_REVIEW_ROUTE,
        "task_type": CANDIDATE_PRODUCTION_PROMOTION_REVIEW_TASK_TYPE,
        "task_id": task_id or "",
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
        "explicit_production_promotion_review_done": explicit_review,
        "operator_approved": operator_approved,
        "button_gated": True,
        "local_review_only": True,
        "local_review_ready": local_ready,
        "ready_to_mark_production_radar_replacement_complete": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "production_replacement_review_ready": production_review_ready,
        "production_promotion_dry_run_visible": promotion_dry_run_visible,
        "legacy_retirement_review_visible": legacy_review_visible,
        "durable_evidence_recipe_visible": durable_recipe_visible,
        "production_stage_manifest_visible": stage_manifest_visible,
        "production_replacement_review_scope_hash": production_review.get("review_scope_hash") or "",
        "production_replacement_review_scope_hash_short": str(production_review.get("review_scope_hash") or "")[:16],
        "promotion_scope_hash": expected_promotion_hash,
        "promotion_scope_hash_short": expected_promotion_hash[:16] if expected_promotion_hash else "",
        "requested_promotion_scope_hash": requested_promotion_hash,
        "requested_promotion_scope_hash_matches_latest": scope_hash_matches,
        "legacy_retirement_scope_hash": legacy_review.get("retirement_scope_hash") or "",
        "legacy_retirement_scope_hash_short": str(legacy_review.get("retirement_scope_hash") or "")[:16],
        "promotion_review_scope_hash": promotion_review_scope_hash,
        "promotion_review_scope_hash_short": promotion_review_scope_hash[:16],
        "promotion_review_scope_hash_algorithm": "sha256",
        "promotion_review_scope_hash_input_includes_secret": False,
        "worker_full_pool_execution_done": worker_full_pool_done,
        "worker_deep_scan_execution_done": worker_deep_scan_done,
        "provider_backed_acceptance_done": provider_backed_done,
        "provider_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "deepseek_model_ledger_complete": model_ledger_done,
        "browser_visual_performance_promoted": browser_promoted,
        "browser_visual_performance_promotion_source": (
            "candidate_browser_qa_review_contract" if browser_promotion_from_local_qa else "production_review"
        )
        if browser_promoted
        else "",
        "durable_evidence_complete": durable_evidence_complete,
        "durable_ci_or_release_evidence_complete": False,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "row_count": len(rows),
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "treat production promotion review as production radar replacement",
            "mark production_radar_replacement_complete from local review",
            "retire legacy radar fallback from this local review",
            "treat local receipts as worker/provider/model/browser evidence",
            "call Tushare/DeepSeek/GitHub from GET cache or React render",
            "start Redis/Celery worker from this review",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This is a button-gated local production-promotion review receipt for LTG-13. It can clear only the local promotion-review checklist item; it does not run workers, call Tushare/DeepSeek/GitHub, execute trades, retire legacy radar, or mark production replacement complete.",
    }
    return receipt, rows


def _attach_candidate_radar_production_promotion_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_production_promotion_review_receipt"))
    if existing.get("schema_version") == CANDIDATE_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("candidate_radar_production_promotion_review_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
        durable_recipe = _as_dict(view.get("candidate_radar_durable_evidence_recipe"))
        provider_ledger_ready = bool(
            durable_recipe.get("provider_call_ledger_evidence_done") is True
            or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
        )
        if receipt.get("explicit_production_promotion_review_done") is True and (
            receipt.get("browser_visual_performance_promoted") is not True
            or (provider_ledger_ready and receipt.get("provider_call_ledger_evidence_done") is not True)
        ):
            refreshed_receipt, refreshed_rows = _candidate_radar_production_promotion_review_receipt(
                view,
                payload_safe={
                    "operator_approved": receipt.get("operator_approved") is True,
                    "promotion_scope_hash": receipt.get("requested_promotion_scope_hash")
                    or receipt.get("promotion_scope_hash")
                    or "",
                    "reviewer": receipt.get("reviewer") or "local_operator",
                },
                explicit_review=True,
                task_id=str(receipt.get("task_id") or ""),
                reviewed_at=str(receipt.get("reviewed_at") or ""),
            )
            if (
                refreshed_receipt.get("browser_visual_performance_promoted") is True
                or refreshed_receipt.get("provider_call_ledger_evidence_done") is True
            ):
                receipt = refreshed_receipt
                rows = refreshed_rows
    else:
        receipt, rows = _candidate_radar_production_promotion_review_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_production_promotion_review_row_count"] = len(rows)
    counts["candidate_radar_production_promotion_review_local_blocker_count"] = receipt.get(
        "local_blocker_count", 0
    )
    counts["candidate_radar_production_promotion_review_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_production_promotion_review_ready"] = receipt.get("local_review_ready") is True
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_production_promotion_review_is_button_gated"] = True
    policy["candidate_radar_production_promotion_review_is_local"] = True
    policy["candidate_radar_production_promotion_review_does_not_start_worker"] = True
    policy["candidate_radar_production_promotion_review_calls_no_provider_model_github"] = True
    policy["candidate_radar_production_promotion_review_is_not_production_replacement"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_promotion_review_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_production_promotion_review_missing"),
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar production promotion review 只审查本地 promotion 边界；不会运行 worker、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_production_promotion_review_receipt"] = receipt
    view["candidate_radar_production_promotion_review_rows"] = rows
    return view


def _candidate_radar_legacy_retirement_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    local_blocker: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "recommended_order": int(recommended_order),
        "evidence": evidence,
        "next_action": next_action,
        "legacy_retirement_review_only": True,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "production_radar_replacement_complete": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_legacy_retirement_review_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _as_dict(payload_safe)
    operator_approved = _coerce_bool(
        payload.get("operator_approved")
        or payload.get("approved_by_user")
        or payload.get("user_approved")
        or payload.get("approved"),
        False,
    )
    production_review = _as_dict(packet.get("candidate_radar_production_replacement_review_receipt"))
    promotion_dry_run = _as_dict(packet.get("candidate_radar_production_promotion_dry_run_receipt"))
    durable_recipe = _as_dict(packet.get("candidate_radar_durable_evidence_recipe"))
    stage_manifest = _as_dict(packet.get("candidate_radar_production_stage_scope_manifest"))
    gap_triage = _as_dict(packet.get("replacement_gap_triage_contract"))
    production_review_ready = production_review.get("local_review_ready") is True
    promotion_review_visible = promotion_dry_run.get("ready_for_local_promotion_review") is True
    durable_recipe_visible = durable_recipe.get("local_recipe_ready") is True
    stage_manifest_visible = stage_manifest.get("local_manifest_ready") is True
    no_loss_visible = _as_dict(packet.get("no_feature_loss_acceptance_contract")).get(
        "local_no_feature_loss_contract_ready"
    ) is True
    legacy_fallback_required = True
    worker_full_pool_done = (
        production_review.get("worker_full_pool_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_full_pool_execution")
    )
    worker_deep_scan_done = (
        production_review.get("worker_deep_scan_execution_done") is True
        or _candidate_stage_direct_evidence_done(packet, "worker_deep_scan_execution")
    )
    provider_backed_done = (
        production_review.get("provider_backed_acceptance_done") is True
        or _candidate_stage_direct_evidence_done(packet, "provider_parity_acceptance")
    )
    provider_call_ledger_evidence_done = bool(
        durable_recipe.get("provider_call_ledger_evidence_done") is True
        or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
        or provider_backed_done
    )
    model_ledger_done = production_review.get("deepseek_model_ledger_complete") is True
    browser_promoted = (
        production_review.get("browser_visual_performance_promoted") is True
        or _candidate_stage_direct_evidence_done(packet, "browser_visual_performance_promotion")
    )
    durable_evidence_complete = production_review.get("durable_evidence_complete") is True
    production_complete = False
    safety_ready = bool(
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("external_calls_triggered") is not True
        and packet.get("tushare_called") is not True
        and packet.get("deepseek_called") is not True
        and packet.get("github_called") is not True
        and packet.get("contains_secret") is not True
    )
    rows = [
        _candidate_radar_legacy_retirement_review_row(
            "explicit_legacy_retirement_review_task",
            "passed_explicit_post" if explicit_review else "blocked_missing_explicit_post",
            passed=explicit_review,
            local_blocker=not explicit_review,
            production_blocker=False,
            evidence=f"route={CANDIDATE_LEGACY_RETIREMENT_REVIEW_ROUTE}; task_id={task_id or '--'}",
            next_action="Run this review only from the explicit POST/button gate.",
            recommended_order=1,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            local_blocker=explicit_review and not operator_approved,
            production_blocker=False,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before creating the legacy retirement review receipt.",
            recommended_order=2,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "production_replacement_review_visible",
            "passed_replacement_review_visible" if production_review_ready else "blocked_replacement_review_required",
            passed=production_review_ready,
            local_blocker=not production_review_ready,
            production_blocker=False,
            evidence=f"status={production_review.get('status')}; local_review_ready={production_review_ready}",
            next_action="Run Candidate Radar production replacement review before legacy retirement review.",
            recommended_order=3,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "production_promotion_dry_run_visible",
            "passed_promotion_dry_run_visible" if promotion_review_visible else "blocked_promotion_dry_run_required",
            passed=promotion_review_visible,
            local_blocker=not promotion_review_visible,
            production_blocker=False,
            evidence=f"status={promotion_dry_run.get('status')}; ready={promotion_review_visible}",
            next_action="Bind legacy retirement review to a local production promotion dry-run scope.",
            recommended_order=4,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "durable_evidence_recipe_visible",
            "passed_durable_recipe_visible" if durable_recipe_visible else "blocked_durable_recipe_required",
            passed=durable_recipe_visible,
            local_blocker=not durable_recipe_visible,
            production_blocker=False,
            evidence=f"status={durable_recipe.get('status')}; blockers={durable_recipe.get('durable_evidence_blocker_count')}",
            next_action="Keep durable evidence requirements visible before any legacy retirement decision.",
            recommended_order=5,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "production_stage_manifest_visible",
            "passed_stage_manifest_visible" if stage_manifest_visible else "blocked_stage_manifest_required",
            passed=stage_manifest_visible,
            local_blocker=not stage_manifest_visible,
            production_blocker=False,
            evidence=f"status={stage_manifest.get('status')}; pending={stage_manifest.get('pending_stage_count')}",
            next_action="Keep the production stage manifest visible until all direct evidence is present.",
            recommended_order=6,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "no_feature_loss_surface_visible",
            "passed_no_feature_loss_visible" if no_loss_visible else "blocked_no_feature_loss_required",
            passed=no_loss_visible,
            local_blocker=not no_loss_visible,
            production_blocker=False,
            evidence=f"status={_as_dict(packet.get('no_feature_loss_acceptance_contract')).get('status')}",
            next_action="Keep no-feature-loss gaps visible before retiring the old radar path.",
            recommended_order=7,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "worker_full_pool_execution_required",
            "completed" if worker_full_pool_done else "pending_worker_full_pool_execution",
            passed=worker_full_pool_done,
            local_blocker=False,
            production_blocker=not worker_full_pool_done,
            evidence=f"worker_full_pool_execution_done={worker_full_pool_done}",
            next_action="Attach real worker-backed full-pool execution before retiring legacy radar.",
            recommended_order=8,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "worker_deep_scan_execution_required",
            "completed" if worker_deep_scan_done else "pending_worker_deep_scan_execution",
            passed=worker_deep_scan_done,
            local_blocker=False,
            production_blocker=not worker_deep_scan_done,
            evidence=f"worker_deep_scan_execution_done={worker_deep_scan_done}",
            next_action="Attach real worker-backed deep-scan execution before retiring legacy radar.",
            recommended_order=9,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "provider_backed_parity_required",
            "provider_call_ledger_observed"
            if provider_call_ledger_evidence_done
            else "pending_provider_backed_parity",
            passed=provider_call_ledger_evidence_done,
            local_blocker=False,
            production_blocker=not provider_call_ledger_evidence_done,
            evidence=(
                f"provider_backed_acceptance_done={provider_backed_done}; "
                f"provider_call_ledger_evidence_done={provider_call_ledger_evidence_done}"
            ),
            next_action="Attach provider-backed parity call ledger before retiring legacy radar.",
            recommended_order=10,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "deepseek_model_ledger_if_enabled_required",
            "completed" if model_ledger_done else "pending_model_ledger",
            passed=model_ledger_done,
            local_blocker=False,
            production_blocker=True,
            evidence=f"deepseek_model_ledger_complete={model_ledger_done}",
            next_action="If DeepSeek is enabled for radar, attach model ledger, sanitizer, parse-failed, and cost evidence.",
            recommended_order=11,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "browser_visual_performance_promotion_required",
            "promoted" if browser_promoted else "pending_browser_visual_performance_promotion",
            passed=browser_promoted,
            local_blocker=False,
            production_blocker=not browser_promoted,
            evidence=f"browser_visual_performance_promoted={browser_promoted}",
            next_action="Promote durable browser visual/performance evidence before legacy retirement.",
            recommended_order=12,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "durable_ci_or_release_evidence_required",
            "complete" if durable_evidence_complete else "pending_durable_release_evidence",
            passed=durable_evidence_complete,
            local_blocker=False,
            production_blocker=not durable_evidence_complete,
            evidence=f"durable_evidence_complete={durable_evidence_complete}",
            next_action="Attach durable local/CI/release evidence before retiring legacy radar.",
            recommended_order=13,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "legacy_fallback_required_until_direct_evidence",
            "passed_legacy_fallback_retained" if legacy_fallback_required else "blocked_legacy_fallback_missing",
            passed=legacy_fallback_required,
            local_blocker=not legacy_fallback_required,
            production_blocker=False,
            evidence=f"legacy_fallback_required={legacy_fallback_required}; triage={gap_triage.get('status')}",
            next_action="Keep legacy/admin/debug fallback available until direct production evidence clears.",
            recommended_order=14,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "production_completion_stays_blocked",
            "blocked_until_direct_evidence",
            passed=False,
            local_blocker=False,
            production_blocker=True,
            evidence="Legacy retirement review is a local receipt and never marks production_radar_replacement_complete.",
            next_action="Complete real worker/provider/model/browser evidence and a separate promotion review before retirement.",
            recommended_order=15,
        ),
        _candidate_radar_legacy_retirement_review_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects" if safety_ready else "blocked_safety_boundary",
            passed=safety_ready,
            local_blocker=not safety_ready,
            production_blocker=not safety_ready,
            evidence="No provider/model/GitHub calls, no trades, no action mutation, and no secret persistence.",
            next_action="Preserve this boundary when replacing the legacy path later.",
            recommended_order=16,
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    local_ready = explicit_review and operator_approved and not local_blockers
    if not explicit_review:
        status = "candidate_radar_legacy_retirement_review_missing"
        allowed_next_step = "run_button_gated_candidate_radar_legacy_retirement_review"
    elif not operator_approved:
        status = "candidate_radar_legacy_retirement_review_blocked_operator_approval_required"
        allowed_next_step = "rerun_with_operator_approval"
    elif local_blockers:
        status = "candidate_radar_legacy_retirement_review_blocked_local_review"
        allowed_next_step = "restore_required_local_reviews"
    else:
        status = "candidate_radar_legacy_retirement_review_ready_retirement_blocked"
        allowed_next_step = "collect_direct_worker_provider_model_browser_and_release_evidence"
    retirement_scope_input = {
        "schema_version": CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION,
        "production_review_scope_hash": production_review.get("review_scope_hash"),
        "promotion_scope_hash": promotion_dry_run.get("promotion_scope_hash"),
        "production_blockers": production_blockers,
        "local_blockers": local_blockers,
        "production_complete": production_complete,
    }
    retirement_scope_hash = hashlib.sha256(
        json.dumps(_safe_value(retirement_scope_input), ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()
    reviewer = _safe_text(payload.get("reviewer") or payload.get("requested_by") or "local_operator", limit=80)
    receipt = {
        "schema_version": CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_candidate_radar_legacy_retirement_review_no_external_call",
        "ltg": "LTG-13/LTG-10",
        "route": CANDIDATE_LEGACY_RETIREMENT_REVIEW_ROUTE,
        "task_type": CANDIDATE_LEGACY_RETIREMENT_REVIEW_TASK_TYPE,
        "task_id": task_id or "",
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
        "explicit_legacy_retirement_review_done": explicit_review,
        "operator_approved": operator_approved,
        "button_gated": True,
        "local_review_only": True,
        "local_review_ready": local_ready,
        "ready_to_retire_legacy": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "production_radar_replacement_complete": False,
        "production_replacement_review_ready": production_review_ready,
        "production_promotion_dry_run_visible": promotion_review_visible,
        "durable_evidence_recipe_visible": durable_recipe_visible,
        "production_stage_manifest_visible": stage_manifest_visible,
        "no_feature_loss_surface_visible": no_loss_visible,
        "production_replacement_review_scope_hash": production_review.get("review_scope_hash") or "",
        "production_replacement_review_scope_hash_short": str(production_review.get("review_scope_hash") or "")[:16],
        "promotion_scope_hash": promotion_dry_run.get("promotion_scope_hash") or "",
        "promotion_scope_hash_short": str(promotion_dry_run.get("promotion_scope_hash") or "")[:16],
        "retirement_scope_hash": retirement_scope_hash,
        "retirement_scope_hash_short": retirement_scope_hash[:16],
        "retirement_scope_hash_algorithm": "sha256",
        "retirement_scope_hash_input_includes_secret": False,
        "worker_full_pool_execution_done": worker_full_pool_done,
        "worker_deep_scan_execution_done": worker_deep_scan_done,
        "provider_backed_acceptance_done": provider_backed_done,
        "provider_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "deepseek_model_ledger_complete": model_ledger_done,
        "browser_visual_performance_promoted": browser_promoted,
        "durable_evidence_complete": durable_evidence_complete,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "row_count": len(rows),
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "treat legacy retirement review as production retirement approval",
            "retire Streamlit or legacy radar fallback from this local review",
            "treat local full-pool receipt as worker full-pool execution",
            "treat local deep review as provider/model deep scan",
            "call Tushare/DeepSeek/GitHub from GET cache or React render",
            "turn candidate rows into buy/sell instructions",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "creates_worker_task": False,
        "creates_provider_model_task": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This is a button-gated local legacy-retirement review receipt for LTG-13/LTG-10. It makes the old radar fallback retirement blocker auditable, but it does not run workers, call Tushare/DeepSeek/GitHub, execute trades, or retire Streamlit/legacy radar.",
    }
    return receipt, rows


def _attach_candidate_radar_legacy_retirement_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    existing = _as_dict(view.get("candidate_radar_legacy_retirement_review_receipt"))
    if existing.get("schema_version") == CANDIDATE_LEGACY_RETIREMENT_REVIEW_SCHEMA_VERSION:
        receipt = dict(existing)
        rows = [
            row
            for row in _as_list(view.get("candidate_radar_legacy_retirement_review_rows"))
            if isinstance(row, dict)
        ]
        if not rows:
            rows = [row for row in _as_list(receipt.get("rows")) if isinstance(row, dict)]
        durable_recipe = _as_dict(view.get("candidate_radar_durable_evidence_recipe"))
        provider_ledger_ready = bool(
            durable_recipe.get("provider_call_ledger_evidence_done") is True
            or durable_recipe.get("provider_parity_call_ledger_evidence_done") is True
        )
        if (
            receipt.get("explicit_legacy_retirement_review_done") is True
            and provider_ledger_ready
            and receipt.get("provider_call_ledger_evidence_done") is not True
        ):
            refreshed_receipt, refreshed_rows = _candidate_radar_legacy_retirement_review_receipt(
                view,
                payload_safe={
                    "operator_approved": receipt.get("operator_approved") is True,
                    "reviewer": receipt.get("reviewer") or "local_operator",
                },
                explicit_review=True,
                task_id=str(receipt.get("task_id") or ""),
                reviewed_at=str(receipt.get("reviewed_at") or ""),
            )
            if refreshed_receipt.get("provider_call_ledger_evidence_done") is True:
                receipt = refreshed_receipt
                rows = refreshed_rows
    else:
        receipt, rows = _candidate_radar_legacy_retirement_review_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_legacy_retirement_review_row_count"] = len(rows)
    counts["candidate_radar_legacy_retirement_review_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_legacy_retirement_review_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_legacy_retirement_review_ready"] = receipt.get("local_review_ready") is True
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_legacy_retirement_review_is_button_gated"] = True
    policy["candidate_radar_legacy_retirement_review_is_local"] = True
    policy["candidate_radar_legacy_retirement_review_does_not_start_worker"] = True
    policy["candidate_radar_legacy_retirement_review_calls_no_provider_model_github"] = True
    policy["candidate_radar_legacy_retirement_review_is_not_legacy_retirement"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_legacy_retirement_review_preview",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=str(receipt.get("status") or "candidate_radar_legacy_retirement_review_missing"),
        )
    )
    warnings = [str(item) for item in _as_list(view.get("warnings"))]
    warning = "Candidate Radar legacy retirement review 只审查本地退场边界；不会运行 worker、调用 Tushare/DeepSeek/GitHub、退掉 legacy 或完成生产替代。"
    if warning not in warnings:
        warnings.append(warning)
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["warnings"] = warnings
    view["candidate_radar_legacy_retirement_review_receipt"] = receipt
    view["candidate_radar_legacy_retirement_review_rows"] = rows
    return view


def _result_delta_clarity_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    user_visible: bool = True,
    gap_visible: bool = False,
    production_pending: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "user_visible": bool(user_visible),
        "gap_visible": bool(gap_visible),
        "production_pending": bool(production_pending),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_delta_signature(candidate_rows: list[dict[str, Any]]) -> str:
    compact_rows = [
        {
            "rank": row.get("rank"),
            "ticker": row.get("ticker"),
            "score": row.get("score"),
            "status_label": row.get("status_label"),
            "action_state": row.get("action_state"),
            "data_gaps": row.get("data_gaps"),
        }
        for row in candidate_rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT]
    ]
    serialized = json.dumps(compact_rows, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _delta_candidate_key(row: Mapping[str, Any], fallback_index: int) -> str:
    key = _first_non_empty(row, ["ticker", "ts_code", "code", "stock_code", "symbol"])
    return _safe_text(key, limit=32).upper() or f"ROW-{fallback_index}"


def _delta_candidate_map(candidate_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(candidate_rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT], start=1):
        key = _delta_candidate_key(row, index)
        if key in mapped:
            continue
        mapped[key] = {
            "ticker": key,
            "rank": row.get("rank") or index,
            "score": row.get("score"),
            "status_label": row.get("status_label"),
            "action_state": row.get("action_state"),
        }
    return mapped


def _previous_candidate_rows_from_packet(previous_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in _as_list(previous_packet.get("candidate_rows")) if isinstance(row, Mapping)]
    if rows:
        return rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT]
    candidates = _as_list(previous_packet.get("candidates"))
    return _candidate_rows(candidates)


def _previous_cache_candidate_diff(
    previous_packet: Mapping[str, Any] | None,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_available = isinstance(previous_packet, Mapping) and bool(previous_packet)
    previous_rows = _previous_candidate_rows_from_packet(previous_packet or {}) if previous_available else []
    current_map = _delta_candidate_map(candidate_rows)
    previous_map = _delta_candidate_map(previous_rows)
    current_keys = list(current_map.keys())
    previous_keys = list(previous_map.keys())
    added = [key for key in current_keys if key not in previous_map]
    removed = [key for key in previous_keys if key not in current_map]
    shared = [key for key in current_keys if key in previous_map]
    rank_changed = [key for key in shared if current_map[key].get("rank") != previous_map[key].get("rank")]
    score_changed = [key for key in shared if current_map[key].get("score") != previous_map[key].get("score")]
    status_changed = [
        key
        for key in shared
        if current_map[key].get("status_label") != previous_map[key].get("status_label")
        or current_map[key].get("action_state") != previous_map[key].get("action_state")
    ]
    diff_rows: list[dict[str, Any]] = []
    for key in added[:30]:
        diff_rows.append(
            {
                "change_type": "added",
                "ticker": key,
                "previous_rank": None,
                "current_rank": current_map[key].get("rank"),
                "previous_score": None,
                "current_score": current_map[key].get("score"),
                "user_visible": True,
            }
        )
    for key in removed[:30]:
        diff_rows.append(
            {
                "change_type": "removed",
                "ticker": key,
                "previous_rank": previous_map[key].get("rank"),
                "current_rank": None,
                "previous_score": previous_map[key].get("score"),
                "current_score": None,
                "user_visible": True,
            }
        )
    for key in sorted(set(rank_changed + score_changed + status_changed))[:30]:
        diff_rows.append(
            {
                "change_type": "updated",
                "ticker": key,
                "previous_rank": previous_map[key].get("rank"),
                "current_rank": current_map[key].get("rank"),
                "previous_score": previous_map[key].get("score"),
                "current_score": current_map[key].get("score"),
                "rank_changed": key in rank_changed,
                "score_changed": key in score_changed,
                "status_changed": key in status_changed,
                "user_visible": True,
            }
        )
    for row in diff_rows:
        row.update(
            {
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    changed_count = len(added) + len(removed) + len(set(rank_changed + score_changed + status_changed))
    previous_signature = str(_as_dict(previous_packet or {}).get("result_delta_clarity_contract", {}).get("candidate_delta_signature") or "")
    return {
        "previous_cache_available": previous_available,
        "previous_cache_diff_done": previous_available,
        "previous_scan_mode": _safe_text(_as_dict(previous_packet or {}).get("scan_mode"), limit=40),
        "previous_cache_source": _safe_text(_as_dict(previous_packet or {}).get("cache_source"), limit=60),
        "previous_candidate_delta_signature": previous_signature or _candidate_delta_signature(previous_rows),
        "previous_candidate_count": len(previous_rows),
        "candidate_added_count": len(added),
        "candidate_removed_count": len(removed),
        "candidate_rank_changed_count": len(rank_changed),
        "candidate_score_changed_count": len(score_changed),
        "candidate_status_changed_count": len(status_changed),
        "candidate_unchanged_count": max(0, len(shared) - len(set(rank_changed + score_changed + status_changed))),
        "candidate_changed_count": changed_count,
        "added_tickers": added[:20],
        "removed_tickers": removed[:20],
        "rank_changed_tickers": rank_changed[:20],
        "score_changed_tickers": score_changed[:20],
        "status_changed_tickers": status_changed[:20],
        "diff_rows": diff_rows,
        "diff_row_count": len(diff_rows),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _result_delta_clarity_contract(
    *,
    scan_mode: str,
    candidate_rows: list[dict[str, Any]],
    counts: Mapping[str, Any],
    coverage: Mapping[str, Any],
    scan_execution_summary: Mapping[str, Any],
    scan_acceptance_rows: list[dict[str, Any]],
    runtime_budget_contract: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
    previous_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    acceptance_by_key = {str(row.get("check_key")): row for row in scan_acceptance_rows}
    provider_gap_count = int(scan_execution_summary.get("provider_gap_count") or 0)
    skipped_reason_count = int(coverage.get("skipped_reason_count") or 0)
    truncated_count = int(runtime_budget_contract.get("candidate_display_truncated_count") or 0)
    full_pool_plan_ready = full_pool_scan_plan.get("status") == "full_pool_plan_ready"
    deep_scan_plan_ready = deep_scan_plan.get("status") == "deep_scan_plan_ready"
    previous_diff = _previous_cache_candidate_diff(previous_packet, candidate_rows)
    previous_diff_done = bool(previous_diff.get("previous_cache_diff_done"))
    rows = [
        _result_delta_clarity_row(
            "candidate_count_and_mix_visible",
            "passed",
            passed=True,
            evidence=(
                f"candidate_count={counts.get('candidate_count')}; "
                f"ready={counts.get('ready_count')}; observe={counts.get('observe_count')}; verify={counts.get('verify_count')}"
            ),
        ),
        _result_delta_clarity_row(
            "candidate_display_cap_visible",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            evidence=(
                f"displayed={runtime_budget_contract.get('candidate_displayed_count')}; "
                f"limit={runtime_budget_contract.get('display_candidate_limit')}; truncated={truncated_count}"
            ),
            gap_visible=bool(truncated_count),
        ),
        _result_delta_clarity_row(
            "skipped_reason_visibility",
            "gap_reported" if skipped_reason_count else "passed",
            passed=True,
            evidence=f"skipped_reason_count={skipped_reason_count}",
            gap_visible=bool(skipped_reason_count),
        ),
        _result_delta_clarity_row(
            "provider_gap_visibility",
            "gap_reported" if provider_gap_count else "passed",
            passed=True,
            evidence=f"provider_gap_count={provider_gap_count}",
            gap_visible=bool(provider_gap_count),
        ),
        _result_delta_clarity_row(
            "freshness_state_visibility",
            str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "unknown"),
            passed=True,
            evidence=f"freshness={freshness_state.get('source') or 'missing'}:{freshness_state.get('state') or 'unknown'}",
            gap_visible=str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "") != "passed",
        ),
        _result_delta_clarity_row(
            "scan_mode_transition_visibility",
            "passed",
            passed=True,
            evidence=(
                f"scan_mode={scan_mode}; family={scan_execution_summary.get('scan_family')}; "
                f"fallback={scan_execution_summary.get('unsupported_scan_mode_fallback')}"
            ),
        ),
        _result_delta_clarity_row(
            "local_pool_delta_visibility",
            "input_reported" if local_pool_audit else "not_applicable",
            passed=True,
            evidence=(
                f"input={local_pool_audit.get('input_candidate_count')}; "
                f"normalized={local_pool_audit.get('normalized_candidate_count')}; "
                f"skipped={local_pool_audit.get('skipped_candidate_count')}"
            )
            if local_pool_audit
            else "current scan did not consume local pool input.",
            gap_visible=bool(local_pool_audit and local_pool_audit.get("skipped_candidate_count")),
        ),
        _result_delta_clarity_row(
            "full_pool_deep_scan_boundary_visibility",
            "plan_only" if full_pool_plan_ready or deep_scan_plan_ready else "pending",
            passed=True,
            evidence=(
                f"full_pool_plan_ready={full_pool_plan_ready}; full_pool_scan_done={full_pool_scan_plan.get('full_pool_scan_done') is True}; "
                f"deep_scan_plan_ready={deep_scan_plan_ready}; deep_scan_done={deep_scan_plan.get('deep_scan_done') is True}"
            ),
            gap_visible=not (full_pool_scan_plan.get("full_pool_scan_done") is True and deep_scan_plan.get("deep_scan_done") is True),
        ),
        _result_delta_clarity_row(
            "previous_cache_diff_pending",
            "completed_previous_cache_diff" if previous_diff_done else "pending_previous_cache_diff",
            passed=previous_diff_done,
            evidence=(
                f"previous_available={previous_diff.get('previous_cache_available')}; "
                f"added={previous_diff.get('candidate_added_count')}; removed={previous_diff.get('candidate_removed_count')}; "
                f"rank_changed={previous_diff.get('candidate_rank_changed_count')}; score_changed={previous_diff.get('candidate_score_changed_count')}"
            ),
            gap_visible=bool(previous_diff.get("candidate_changed_count")),
            production_pending=not previous_diff_done,
        ),
        _result_delta_clarity_row(
            "browser_visual_delta_qa_pending",
            "pending_visual_qa",
            passed=False,
            evidence="Browser viewport/performance QA is not executed by the local cache contract.",
            production_pending=True,
        ),
        _result_delta_clarity_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            evidence="Result change cues never modify strategy action, holdings, or orders.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if not row.get("passed") and not row.get("production_pending")]
    visible_gaps = [row["criterion"] for row in rows if row.get("gap_visible")]
    production_pending = [row["criterion"] for row in rows if row.get("production_pending")]
    local_ready = not local_blockers
    return {
        "schema_version": "candidate_radar_result_delta_clarity.v1",
        "status": (
            "result_delta_clarity_local_ready_browser_qa_pending"
            if local_ready and previous_diff_done
            else "result_delta_clarity_local_ready_previous_diff_pending"
            if local_ready
            else "result_delta_clarity_blocked"
        ),
        "scope": (
            "local_result_delta_visibility_and_previous_cache_diff_not_browser_visual_qa"
            if previous_diff_done
            else "local_result_delta_visibility_contract_not_previous_cache_diff_or_browser_visual_qa"
        ),
        "ltg": "LTG-13/LTG-14",
        "scan_mode": scan_mode,
        "candidate_delta_signature": _candidate_delta_signature(candidate_rows),
        "local_result_delta_clarity_ready": local_ready,
        "previous_cache_available": bool(previous_diff.get("previous_cache_available")),
        "previous_cache_diff_done": previous_diff_done,
        "previous_scan_mode": previous_diff.get("previous_scan_mode"),
        "previous_cache_source": previous_diff.get("previous_cache_source"),
        "previous_candidate_delta_signature": previous_diff.get("previous_candidate_delta_signature"),
        "previous_candidate_count": previous_diff.get("previous_candidate_count"),
        "candidate_added_count": previous_diff.get("candidate_added_count"),
        "candidate_removed_count": previous_diff.get("candidate_removed_count"),
        "candidate_rank_changed_count": previous_diff.get("candidate_rank_changed_count"),
        "candidate_score_changed_count": previous_diff.get("candidate_score_changed_count"),
        "candidate_status_changed_count": previous_diff.get("candidate_status_changed_count"),
        "candidate_unchanged_count": previous_diff.get("candidate_unchanged_count"),
        "candidate_changed_count": previous_diff.get("candidate_changed_count"),
        "added_tickers": previous_diff.get("added_tickers"),
        "removed_tickers": previous_diff.get("removed_tickers"),
        "rank_changed_tickers": previous_diff.get("rank_changed_tickers"),
        "score_changed_tickers": previous_diff.get("score_changed_tickers"),
        "status_changed_tickers": previous_diff.get("status_changed_tickers"),
        "previous_cache_diff_row_count": previous_diff.get("diff_row_count"),
        "browser_visual_delta_qa_done": False,
        "production_radar_replacement_complete": False,
        "candidate_count": len(candidate_rows),
        "candidate_input_count": int(coverage_detail.get("candidate_input_count") or 0),
        "candidate_display_truncated_count": truncated_count,
        "skipped_reason_count": skipped_reason_count,
        "provider_gap_count": provider_gap_count,
        "visible_gap_count": len(visible_gaps),
        "production_pending_count": len(production_pending),
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "local_blockers": local_blockers,
        "visible_gaps": visible_gaps,
        "production_pending_items": production_pending,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "previous_cache_diff_rows": previous_diff.get("diff_rows") or [],
        "note": "This contract makes candidate result-change cues visible without rescoring, provider refreshes, timers, browser QA, or trade/action mutation. When a previous persisted packet exists, it also computes a local previous-cache diff.",
    }


def _full_pool_filter_rows(payload_safe: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, default in FULL_POOL_FILTER_DEFAULTS.items():
        value = payload_safe.get(key, default)
        if isinstance(value, str):
            enabled = value.strip().lower() not in {"false", "0", "no", "off"}
        else:
            enabled = bool(value)
        rows.append(
            {
                "filter_key": key,
                "enabled": enabled,
                "default_enabled": default,
                "source": "payload" if key in payload_safe else "default",
                "effect": "candidate_exclusion_before_scoring",
                "applied_now": False,
                "requires_future_scan_execution": True,
                "does_not_scan_full_market_on_plan": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    return rows


def _full_pool_stage_rows(
    *,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provider_gap_count = sum(1 for row in provider_rows if row.get("coverage_status") != "available")
    freshness_missing = freshness_state.get("source") == "missing"
    return [
        {
            "stage": "load_universe",
            "status": "planned_worker_required",
            "source": "future local universe dataset or explicit task payload",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "full_pool_universe_not_loaded_in_plan_task",
        },
        {
            "stage": "apply_filters",
            "status": "planned_filters_declared",
            "source": "full_pool_filter_rows",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "",
        },
        {
            "stage": "read_local_storage",
            "status": "planned_storage_contract_required",
            "source": ",".join(FULL_POOL_REQUIRED_STORAGE_DATASETS),
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "storage_query_contracts_must_be_consumed_by_future_worker",
        },
        {
            "stage": "provider_refresh",
            "status": "blocked_until_explicit_provider_tasks" if provider_gap_count else "optional_if_cache_fresh",
            "source": "Tushare button-gated refresh tasks",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "provider_gaps_present" if provider_gap_count else "",
        },
        {
            "stage": "freshness_gate",
            "status": "blocked_until_current_freshness" if freshness_missing else "planned_gate_required",
            "source": "data_freshness/trade_cal",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "freshness_state_missing" if freshness_missing else "",
        },
        {
            "stage": "score_candidates",
            "status": "planned_research_only",
            "source": "legacy radar scoring parity map",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "scoring_not_executed_in_plan_task",
        },
        {
            "stage": "write_candidate_packet",
            "status": "planned_after_worker_scan",
            "source": PACKET_KEY,
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "full_pool_packet_not_written_by_plan",
        },
    ]


def _full_pool_blocker_rows(
    *,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "blocker_key": "worker_required",
            "severity": "production_required",
            "status": "blocked",
            "message": "full_pool_scan must run through future worker/task execution, not page render.",
            "blocks_full_pool_scan": True,
        }
    ]
    if freshness_state.get("source") == "missing":
        rows.append(
            {
                "blocker_key": "freshness_missing",
                "severity": "freshness_gap",
                "status": "blocked",
                "message": "freshness_state is missing; full-pool candidates would be research-only.",
                "blocks_full_pool_scan": True,
            }
        )
    for row in provider_rows:
        if row.get("coverage_status") == "available":
            continue
        rows.append(
            {
                "blocker_key": f"provider_{row.get('signal_group')}",
                "severity": row.get("severity") or "coverage_gap",
                "status": row.get("coverage_status") or "unknown",
                "message": f"{row.get('label')} provider coverage is {row.get('coverage_status')}.",
                "blocks_full_pool_scan": True,
            }
        )
    missing_groups = [row.get("group") for row in source_rows if not row.get("present")]
    if missing_groups:
        rows.append(
            {
                "blocker_key": "legacy_signal_group_gaps",
                "severity": "parity_gap",
                "status": "missing_reported",
                "message": "Legacy radar signal groups are not all mapped in current cache.",
                "missing_signal_groups": missing_groups,
                "blocks_full_pool_scan": False,
            }
        )
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _full_pool_required_signal_rows(provider_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_group = {str(row.get("signal_group") or ""): row for row in provider_rows}
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        coverage = by_group.get(str(requirement["signal_group"])) or {}
        rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "coverage_status": coverage.get("coverage_status") or "missing_provider_data",
                "matched_provider_row_count": coverage.get("matched_provider_row_count") or 0,
                "ready_for_full_pool": coverage.get("coverage_status") == "available",
                "requires_explicit_provider_task": coverage.get("coverage_status") != "available",
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _build_full_pool_scan_plan(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    provider_rows = _provider_coverage_rows(snapshot_map)
    freshness_state = _candidate_freshness_state(snapshot_map)
    source_rows = _source_group_rows(snapshot_map)
    filter_rows = _full_pool_filter_rows(payload_safe)
    blocker_rows = _full_pool_blocker_rows(
        provider_rows=provider_rows,
        freshness_state=freshness_state,
        source_rows=source_rows,
    )
    stage_rows = _full_pool_stage_rows(provider_rows=provider_rows, freshness_state=freshness_state)
    signal_rows = _full_pool_required_signal_rows(provider_rows)
    blocking_count = sum(1 for row in blocker_rows if row.get("blocks_full_pool_scan"))
    return {
        "schema_version": "candidate_radar_full_pool_plan.v1",
        "status": "full_pool_plan_ready",
        "task_type": "run_candidate_radar_full_pool_plan",
        "created_at": now,
        "requested_scan_mode": "full_pool_scan",
        "full_pool_scan_done": False,
        "full_pool_validation_done": False,
        "worker_task_required": True,
        "worker_task_consumption_plan_ready": True,
        "page_render_starts_full_pool": False,
        "cache_get_starts_full_pool": False,
        "provider_refresh_executed": False,
        "candidate_scoring_executed": False,
        "candidate_packet_written_by_plan": False,
        "storage_datasets_required": list(FULL_POOL_REQUIRED_STORAGE_DATASETS),
        "required_signal_group_count": len(signal_rows),
        "ready_signal_group_count": sum(1 for row in signal_rows if row.get("ready_for_full_pool")),
        "provider_gap_count": sum(1 for row in signal_rows if not row.get("ready_for_full_pool")),
        "blocking_issue_count": blocking_count,
        "filter_rows": filter_rows,
        "stage_rows": stage_rows,
        "required_signal_rows": signal_rows,
        "blocker_rows": blocker_rows,
        "legacy_signal_group_rows": source_rows,
        "freshness_state": freshness_state,
        "research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Full-pool plan only records prerequisites and blockers; it does not scan the market or produce buy candidates.",
    }


def _full_pool_local_execution_row(
    receipt_key: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
) -> dict[str, Any]:
    return {
        "receipt_key": receipt_key,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _full_pool_local_execution_receipt(
    *,
    scan_mode: str,
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    full_pool_scan_plan: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    is_local_full_pool = scan_mode == "full_pool_local_scan"
    normalized_count = int(local_pool_audit.get("normalized_candidate_count") or 0)
    input_count = int(local_pool_audit.get("input_candidate_count") or 0)
    truncated_count = int(local_pool_audit.get("truncated_candidate_count") or 0)
    freshness = _as_dict(coverage.get("freshness_state"))
    provider_gap_count = int(_as_dict(coverage.get("coverage_detail_summary")).get("provider_blocked_group_count") or 0) + int(
        _as_dict(coverage.get("coverage_detail_summary")).get("stale_input_group_count") or 0
    ) + int(_as_dict(coverage.get("coverage_detail_summary")).get("missing_provider_data_group_count") or 0)
    local_execution_done = is_local_full_pool and normalized_count > 0
    rows = [
        _full_pool_local_execution_row(
            "explicit_post_task_required",
            "passed" if is_local_full_pool else "not_applicable",
            passed=is_local_full_pool,
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; page_render_starts_full_pool=false; cache_get_starts_full_pool=false",
        ),
        _full_pool_local_execution_row(
            "local_universe_consumed",
            "passed" if normalized_count else "blocked_empty_local_universe",
            passed=normalized_count > 0,
            production_blocker=not local_execution_done,
            evidence=f"input={input_count}; normalized={normalized_count}; source={local_pool_audit.get('input_source')}",
        ),
        _full_pool_local_execution_row(
            "display_cap_visible",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            production_blocker=False,
            evidence=f"displayed={len(candidate_rows)}; input_limit={local_pool_audit.get('max_local_candidates')}; truncated={truncated_count}",
        ),
        _full_pool_local_execution_row(
            "provider_not_refreshed",
            "provider_gaps_visible" if provider_gap_count else "passed",
            passed=True,
            production_blocker=True,
            evidence=f"provider_gap_count={provider_gap_count}; provider_refresh_executed=false",
        ),
        _full_pool_local_execution_row(
            "freshness_boundary_visible",
            "research_only_reported" if freshness.get("source") == "missing" else "visible",
            passed=True,
            production_blocker=True,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
        ),
        _full_pool_local_execution_row(
            "production_full_market_acceptance_pending",
            "pending_provider_worker_browser_acceptance",
            passed=False,
            production_blocker=True,
            evidence=(
                f"local_execution_done={local_execution_done}; "
                f"full_pool_plan_status={full_pool_scan_plan.get('status')}; provider_backed_acceptance_done=false"
            ),
        ),
        _full_pool_local_execution_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            production_blocker=False,
            evidence="Local full-pool execution writes research candidates only and never mutates strategy action, holdings, or orders.",
        ),
    ]
    local_blockers = [row["receipt_key"] for row in rows if not row.get("passed") and not row.get("production_blocker")]
    production_blockers = [row["receipt_key"] for row in rows if row.get("production_blocker")]
    receipt = {
        "schema_version": "candidate_radar_full_pool_local_execution_receipt.v1",
        "status": (
            "full_pool_local_execution_ready_production_pending"
            if local_execution_done
            else "full_pool_local_execution_blocked_empty_universe"
            if is_local_full_pool
            else "full_pool_local_execution_not_run"
        ),
        "scope": "explicit_local_universe_execution_not_provider_backed_full_market_acceptance",
        "ltg": "LTG-13",
        "scan_mode": scan_mode,
        "local_full_pool_execution_done": local_execution_done,
        "production_full_pool_scan_done": False,
        "full_pool_scan_done": False,
        "provider_backed_acceptance_done": False,
        "worker_backed_execution_done": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "input_candidate_count": input_count,
        "normalized_candidate_count": normalized_count,
        "candidate_row_count": len(candidate_rows),
        "truncated_candidate_count": truncated_count,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "not_allowed_next_steps": [
            "treat_local_full_pool_execution_as_provider_backed_full_market_acceptance",
            "retire_legacy_radar_after_local_execution_only",
            "convert_candidate_rows_to_buy_instruction",
            "refresh_provider_from_full_pool_local_scan",
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This receipt proves only an explicit local-universe Candidate Radar task consumed local candidates and wrote a packet. It is not real provider-backed full-market acceptance.",
    }
    return receipt, rows


def _deep_scan_required_signal_rows(provider_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_group = {str(row.get("signal_group") or ""): row for row in provider_rows}
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        coverage = by_group.get(str(requirement["signal_group"])) or {}
        coverage_status = str(coverage.get("coverage_status") or "missing_provider_data")
        rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "coverage_status": coverage_status,
                "matched_provider_row_count": coverage.get("matched_provider_row_count") or 0,
                "ready_for_deep_scan": coverage_status == "available",
                "gap_visible": coverage_status != "available",
                "requires_explicit_provider_task": coverage_status != "available",
                "does_not_refresh_provider": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _deep_scan_parity_rows(
    *,
    parity_rows: list[dict[str, Any]],
    output_contract_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in parity_rows:
        status = str(row.get("migration_status") or "")
        gap_visible = "missing" in status or "future" in status
        rows.append(
            {
                "kind": "legacy_parity",
                "key": row.get("key"),
                "label": row.get("label"),
                "migration_status": status,
                "ready_for_deep_scan": not gap_visible,
                "blocks_legacy_replacement": gap_visible,
                "gap_visible": gap_visible,
                "target_state": row.get("target_state"),
                "does_not_silently_drop_feature": True,
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    for row in output_contract_rows:
        present = bool(row.get("present"))
        rows.append(
            {
                "kind": "output_contract",
                "key": row.get("field"),
                "label": row.get("field"),
                "migration_status": "mapped" if present else "missing_reported",
                "ready_for_deep_scan": present,
                "blocks_legacy_replacement": not present,
                "gap_visible": not present,
                "target_state": row.get("required_for"),
                "does_not_invent_value": True,
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _deep_scan_stage_rows(
    *,
    candidate_rows: list[dict[str, Any]],
    provider_signal_rows: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provider_gap_count = sum(1 for row in provider_signal_rows if not row.get("ready_for_deep_scan"))
    parity_gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    freshness = str(freshness_state.get("state") or "").lower()
    freshness_ready = freshness_state.get("source") != "missing" and freshness not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    rows = [
        {
            "stage": "load_local_candidate_universe",
            "status": "ready" if candidate_rows else "blocked_missing_local_candidates",
            "executed_now": False,
            "row_count": len(candidate_rows),
            "blocks_deep_scan": not bool(candidate_rows),
            "external_calls_triggered": False,
        },
        {
            "stage": "legacy_feature_parity",
            "status": "ready" if not parity_gap_count else "gaps_visible_do_not_replace_legacy",
            "executed_now": False,
            "gap_count": parity_gap_count,
            "blocks_deep_scan": bool(parity_gap_count),
            "external_calls_triggered": False,
        },
        {
            "stage": "provider_signal_inputs",
            "status": "ready" if not provider_gap_count else "provider_gaps_visible_no_refresh",
            "executed_now": False,
            "gap_count": provider_gap_count,
            "blocks_deep_scan": bool(provider_gap_count),
            "external_calls_triggered": False,
        },
        {
            "stage": "freshness_gate",
            "status": "ready" if freshness_ready else "research_only_until_current_freshness",
            "executed_now": False,
            "freshness_state": freshness_state.get("state") or "unknown",
            "blocks_deep_scan": not freshness_ready,
            "external_calls_triggered": False,
        },
        {
            "stage": "async_worker_execution",
            "status": "future_worker_required",
            "executed_now": False,
            "blocks_deep_scan": True,
            "external_calls_triggered": False,
        },
        {
            "stage": "manual_deep_research_boundary",
            "status": "manual_only_future_task",
            "executed_now": False,
            "blocks_deep_scan": False,
            "external_calls_triggered": False,
        },
        {
            "stage": "write_deep_scan_packet",
            "status": "not_executed_by_plan",
            "executed_now": False,
            "blocks_deep_scan": True,
            "external_calls_triggered": False,
        },
    ]
    for row in rows:
        row.update(
            {
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    return rows


def _deep_scan_blocker_rows(
    *,
    stage_rows: list[dict[str, Any]],
    provider_signal_rows: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in stage_rows:
        if not stage.get("blocks_deep_scan"):
            continue
        rows.append(
            {
                "blocker_key": f"stage_{stage.get('stage')}",
                "severity": "production_required" if stage.get("stage") in {"async_worker_execution", "write_deep_scan_packet"} else "readiness_gap",
                "status": stage.get("status"),
                "message": f"Deep scan stage {stage.get('stage')} is not ready for execution.",
                "blocks_deep_scan": True,
            }
        )
    for row in provider_signal_rows:
        if row.get("ready_for_deep_scan"):
            continue
        rows.append(
            {
                "blocker_key": f"provider_{row.get('signal_group')}",
                "severity": "coverage_gap",
                "status": row.get("coverage_status") or "missing_provider_data",
                "message": f"{row.get('label')} coverage is not ready for deep scan.",
                "blocks_deep_scan": True,
            }
        )
    parity_gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    if parity_gap_count:
        rows.append(
            {
                "blocker_key": "legacy_feature_parity_gaps",
                "severity": "parity_gap",
                "status": "gaps_visible",
                "message": "Legacy radar features are not all mapped; keep Streamlit fallback until gaps are closed.",
                "gap_count": parity_gap_count,
                "blocks_deep_scan": True,
            }
        )
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _build_deep_scan_plan(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    candidates = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
    excluded_candidates = _as_list(radar_packet.get("excluded_candidates"))[:10]
    evidence_recovery_actions = _as_list(snapshot_map.get("next_ticket_evidence_recovery_actions"))[:10]
    candidate_rows = _candidate_rows(candidates)
    provider_rows = _provider_coverage_rows(snapshot_map)
    freshness_state = _candidate_freshness_state(snapshot_map)
    parity_rows_raw = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    output_contract_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    provider_signal_rows = _deep_scan_required_signal_rows(provider_rows)
    parity_rows = _deep_scan_parity_rows(
        parity_rows=parity_rows_raw,
        output_contract_rows=output_contract_rows,
    )
    stage_rows = _deep_scan_stage_rows(
        candidate_rows=candidate_rows,
        provider_signal_rows=provider_signal_rows,
        parity_rows=parity_rows,
        freshness_state=freshness_state,
    )
    blocker_rows = _deep_scan_blocker_rows(
        stage_rows=stage_rows,
        provider_signal_rows=provider_signal_rows,
        parity_rows=parity_rows,
    )
    gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    ready_signal_count = sum(1 for row in provider_signal_rows if row.get("ready_for_deep_scan"))
    return {
        "schema_version": "candidate_radar_deep_scan_plan.v1",
        "status": "deep_scan_plan_ready",
        "task_type": "run_candidate_radar_deep_scan_plan",
        "created_at": now,
        "requested_scan_mode": "deep_scan",
        "requested_depth": _safe_text(payload_safe.get("scan_depth") or "legacy_parity_first", limit=40),
        "deep_scan_done": False,
        "deep_scan_validation_done": False,
        "fast_path_ready": bool(candidate_rows),
        "legacy_feature_loss_guard_ready": gap_count == 0,
        "page_render_starts_deep_scan": False,
        "cache_get_starts_deep_scan": False,
        "provider_refresh_executed": False,
        "candidate_scoring_executed": False,
        "candidate_packet_written_by_plan": False,
        "worker_task_required": True,
        "worker_task_consumption_plan_ready": True,
        "stage_rows": stage_rows,
        "parity_rows": parity_rows,
        "required_signal_rows": provider_signal_rows,
        "blocker_rows": blocker_rows,
        "candidate_row_count": len(candidate_rows),
        "required_signal_group_count": len(provider_signal_rows),
        "ready_signal_group_count": ready_signal_count,
        "provider_gap_count": len(provider_signal_rows) - ready_signal_count,
        "legacy_feature_gap_count": gap_count,
        "blocking_issue_count": sum(1 for row in blocker_rows if row.get("blocks_deep_scan")),
        "research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Deep-scan plan records readiness and feature-loss gaps; it does not execute a deep scan, refresh providers, call DeepSeek, or produce trade instructions.",
    }


def _deep_scan_local_review_row(
    review_key: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
) -> dict[str, Any]:
    return {
        "review_key": review_key,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _deep_scan_local_review_receipt(
    *,
    scan_mode: str,
    candidate_rows: list[dict[str, Any]],
    deep_scan_plan: Mapping[str, Any],
    legacy_parity_acceptance: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    is_local_review = scan_mode == "deep_scan_local_review"
    reviewed_count = len(candidate_rows[:PRIORITY_EXPLANATION_LIMIT]) if is_local_review else 0
    missing_evidence_count = sum(1 for row in candidate_rows[:PRIORITY_EXPLANATION_LIMIT] if _candidate_data_gap_count(row))
    missing_trigger_count = sum(
        1
        for row in candidate_rows[:PRIORITY_EXPLANATION_LIMIT]
        if row.get("trigger_condition") in (None, "", [], {})
        or row.get("invalidation_condition") in (None, "", [], {})
    )
    provider_gap_count = int(deep_scan_plan.get("provider_gap_count") or 0)
    legacy_gap_count = int(legacy_parity_acceptance.get("production_blocker_count") or 0)
    freshness = _as_dict(coverage.get("freshness_state"))
    local_review_done = is_local_review and reviewed_count > 0
    rows = [
        _deep_scan_local_review_row(
            "explicit_post_task_required",
            "passed" if is_local_review else "not_applicable",
            passed=is_local_review,
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; page_render_starts_deep_scan=false; cache_get_starts_deep_scan=false",
        ),
        _deep_scan_local_review_row(
            "local_candidate_evidence_reviewed",
            "passed" if reviewed_count else "blocked_empty_candidates",
            passed=reviewed_count > 0,
            production_blocker=not local_review_done,
            evidence=f"reviewed_candidate_count={reviewed_count}; missing_evidence_count={missing_evidence_count}",
        ),
        _deep_scan_local_review_row(
            "trigger_invalidation_reviewed",
            "gaps_visible" if missing_trigger_count else "passed",
            passed=True,
            production_blocker=bool(missing_trigger_count),
            evidence=f"missing_trigger_or_invalidation_count={missing_trigger_count}",
        ),
        _deep_scan_local_review_row(
            "legacy_parity_gaps_visible",
            "gaps_visible" if legacy_gap_count else "passed",
            passed=True,
            production_blocker=bool(legacy_gap_count),
            evidence=f"legacy_parity_production_blocker_count={legacy_gap_count}",
        ),
        _deep_scan_local_review_row(
            "provider_not_refreshed",
            "provider_gaps_visible" if provider_gap_count else "passed",
            passed=True,
            production_blocker=True,
            evidence=f"provider_gap_count={provider_gap_count}; provider_refresh_executed=false",
        ),
        _deep_scan_local_review_row(
            "deepseek_not_called",
            "passed",
            passed=True,
            production_blocker=True,
            evidence="Deep-scan local review does not call DeepSeek; future model explanation stays manual/button-gated.",
        ),
        _deep_scan_local_review_row(
            "freshness_boundary_visible",
            "research_only_reported" if freshness.get("source") == "missing" else "visible",
            passed=True,
            production_blocker=True,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
        ),
        _deep_scan_local_review_row(
            "production_deep_scan_acceptance_pending",
            "pending_provider_model_worker_browser_acceptance",
            passed=False,
            production_blocker=True,
            evidence=(
                f"local_review_done={local_review_done}; deep_scan_plan_status={deep_scan_plan.get('status')}; "
                "deep_scan_done=false; provider_backed_acceptance_done=false"
            ),
        ),
        _deep_scan_local_review_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            production_blocker=False,
            evidence="Deep-scan local review is research-only and never mutates strategy action, holdings, or orders.",
        ),
    ]
    local_blockers = [row["review_key"] for row in rows if not row.get("passed") and not row.get("production_blocker")]
    production_blockers = [row["review_key"] for row in rows if row.get("production_blocker")]
    receipt = {
        "schema_version": "candidate_radar_deep_scan_local_review_receipt.v1",
        "status": (
            "deep_scan_local_review_ready_production_pending"
            if local_review_done
            else "deep_scan_local_review_blocked_empty_candidates"
            if is_local_review
            else "deep_scan_local_review_not_run"
        ),
        "scope": "explicit_local_candidate_deep_review_not_model_or_provider_execution",
        "ltg": "LTG-13",
        "scan_mode": scan_mode,
        "local_deep_scan_review_done": local_review_done,
        "deep_scan_done": False,
        "deep_scan_validation_done": False,
        "provider_backed_acceptance_done": False,
        "deepseek_called": False,
        "worker_backed_execution_done": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "reviewed_candidate_count": reviewed_count,
        "missing_evidence_count": missing_evidence_count,
        "missing_trigger_or_invalidation_count": missing_trigger_count,
        "provider_gap_count": provider_gap_count,
        "legacy_parity_production_blocker_count": legacy_gap_count,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "not_allowed_next_steps": [
            "treat_local_deep_review_as_deep_scan_done",
            "call_deepseek_from_local_review",
            "refresh_provider_from_deep_scan_local_review",
            "retire_legacy_radar_after_local_review_only",
            "convert_review_rows_to_buy_instruction",
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This receipt reviews local candidate evidence and feature/provider/freshness gaps only. It is not DeepSeek execution, provider-backed acceptance, or production deep_scan completion.",
    }
    return receipt, rows


def _build_candidate_radar_packet(
    snapshot: Mapping[str, Any],
    *,
    mode: str,
    cache_source: str,
    scan_mode: str = "cache_only",
    request_params_safe: dict[str, Any] | None = None,
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
    full_pool_scan_plan: Mapping[str, Any] | None = None,
    deep_scan_plan: Mapping[str, Any] | None = None,
    previous_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    previous_map = _as_dict(previous_packet)
    radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    candidates = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
    candidate_input_count = max(_raw_candidate_input_count(raw_snapshot), len(candidates))
    excluded_candidates = _as_list(radar_packet.get("excluded_candidates"))[:10]
    evidence_recovery_actions = _as_list(snapshot_map.get("next_ticket_evidence_recovery_actions"))[:10]
    candidate_rows = _candidate_rows(candidates)
    previous_candidate_rows = [
        dict(row) for row in _as_list(previous_map.get("candidate_rows")) if isinstance(row, dict)
    ]
    if not candidate_rows and previous_candidate_rows and scan_mode in PERSISTED_TASK_SCAN_MODES:
        candidate_rows = previous_candidate_rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT]
        candidate_input_count = max(candidate_input_count, len(previous_candidate_rows))
    candidate_display_truncated_count = max(0, candidate_input_count - len(candidate_rows))
    counts = _candidate_counts(candidate_rows)
    parity_inventory = _legacy_parity_inventory(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    legacy_parity_rows = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    legacy_output_contract_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    legacy_parity_acceptance_receipt, legacy_parity_acceptance_rows = _legacy_parity_acceptance_receipt(
        parity_inventory=parity_inventory,
        parity_rows=legacy_parity_rows,
        output_contract_rows=legacy_output_contract_rows,
    )
    coverage = _scan_coverage(
        snapshot_available=bool(snapshot),
        snapshot_map=snapshot_map,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        scan_mode=scan_mode,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        candidate_input_count=candidate_input_count,
        candidate_display_truncated_count=candidate_display_truncated_count,
    )
    data_freshness_contract = _candidate_data_freshness_contract(_as_dict(coverage.get("freshness_state")))
    counts["legacy_parity_gap_count"] = parity_inventory["gap_or_future_count"]
    counts["legacy_parity_mapped_count"] = parity_inventory["mapped_or_partial_count"]
    counts["legacy_output_mapped_count"] = parity_inventory["output_contract_mapped_count"]
    counts["legacy_parity_acceptance_row_count"] = legacy_parity_acceptance_receipt["receipt_row_count"]
    counts["legacy_parity_acceptance_production_blocker_count"] = legacy_parity_acceptance_receipt[
        "production_blocker_count"
    ]
    counts["legacy_parity_acceptance_ready_count"] = legacy_parity_acceptance_receipt["production_ready_count"]
    if local_pool_audit:
        counts["local_pool_input_candidate_count"] = local_pool_audit.get("input_candidate_count")
        counts["local_pool_normalized_candidate_count"] = local_pool_audit.get("normalized_candidate_count")
        counts["local_pool_duplicate_candidate_count"] = local_pool_audit.get("duplicate_candidate_count")
    counts["provider_blocked_group_count"] = coverage["coverage_detail_summary"]["provider_blocked_group_count"]
    counts["stale_input_group_count"] = coverage["coverage_detail_summary"]["stale_input_group_count"]
    counts["missing_provider_data_group_count"] = coverage["coverage_detail_summary"]["missing_provider_data_group_count"]
    counts["degraded_mode_active_count"] = coverage["coverage_detail_summary"]["degraded_mode_active_count"]
    counts["universe_size"] = coverage["coverage_detail_summary"]["universe_size"]
    counts["candidate_input_count"] = candidate_input_count
    counts["candidate_display_limit"] = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT
    counts["candidate_display_truncated_count"] = candidate_display_truncated_count
    plan = dict(full_pool_scan_plan or _as_dict(snapshot_map.get("full_pool_scan_plan")))
    deep_plan = dict(deep_scan_plan or _as_dict(snapshot_map.get("deep_scan_plan")))
    full_pool_local_execution_receipt, full_pool_local_execution_rows = _full_pool_local_execution_receipt(
        scan_mode=scan_mode,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
        full_pool_scan_plan=plan,
        coverage=coverage,
    )
    deep_scan_local_review_receipt, deep_scan_local_review_rows = _deep_scan_local_review_receipt(
        scan_mode=scan_mode,
        candidate_rows=candidate_rows,
        deep_scan_plan=deep_plan,
        legacy_parity_acceptance=legacy_parity_acceptance_receipt,
        coverage=coverage,
    )
    previous_full_pool_receipt = _as_dict(previous_map.get("full_pool_local_execution_receipt"))
    if (
        previous_full_pool_receipt.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
        and previous_full_pool_receipt.get("status") != "full_pool_local_execution_not_run"
        and scan_mode != "full_pool_local_scan"
    ):
        full_pool_local_execution_receipt = previous_full_pool_receipt
        full_pool_local_execution_rows = [
            row for row in _as_list(previous_map.get("full_pool_local_execution_rows")) if isinstance(row, dict)
        ] or [row for row in _as_list(previous_full_pool_receipt.get("rows")) if isinstance(row, dict)]
    previous_deep_scan_receipt = _as_dict(previous_map.get("deep_scan_local_review_receipt"))
    if (
        previous_deep_scan_receipt.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
        and previous_deep_scan_receipt.get("status") != "deep_scan_local_review_not_run"
        and scan_mode != "deep_scan_local_review"
    ):
        deep_scan_local_review_receipt = previous_deep_scan_receipt
        deep_scan_local_review_rows = [
            row for row in _as_list(previous_map.get("deep_scan_local_review_rows")) if isinstance(row, dict)
        ] or [row for row in _as_list(previous_deep_scan_receipt.get("rows")) if isinstance(row, dict)]
    search_quant_projection_receipt = _as_dict(snapshot_map.get("search_quant_projection_receipt"))
    search_quant_projection_rows = [
        row for row in _as_list(snapshot_map.get("search_quant_projection_rows")) if isinstance(row, dict)
    ]
    if not search_quant_projection_receipt:
        previous_quant_receipt = _as_dict(previous_map.get("search_quant_projection_receipt"))
        if previous_quant_receipt.get("schema_version") == QUANT_PROJECTION_SCHEMA_VERSION:
            search_quant_projection_receipt = previous_quant_receipt
            search_quant_projection_rows = [
                row for row in _as_list(previous_map.get("search_quant_projection_rows")) if isinstance(row, dict)
            ] or [row for row in _as_list(previous_quant_receipt.get("rows")) if isinstance(row, dict)]
    search_quant_projection_activation_receipt, search_quant_projection_activation_rows = (
        _quant_projection_activation_receipt(search_quant_projection_receipt)
    )
    search_quant_projection_acceptance_dry_run_receipt = _as_dict(
        snapshot_map.get("search_quant_projection_acceptance_dry_run_receipt")
    )
    search_quant_projection_acceptance_dry_run_rows = [
        row
        for row in _as_list(snapshot_map.get("search_quant_projection_acceptance_dry_run_rows"))
        if isinstance(row, dict)
    ]
    search_quant_projection_credential_presence_rows = [
        row
        for row in _as_list(snapshot_map.get("search_quant_projection_credential_presence_rows"))
        if isinstance(row, dict)
    ]
    if not search_quant_projection_acceptance_dry_run_receipt:
        previous_quant_dry_run_receipt = _as_dict(previous_map.get("search_quant_projection_acceptance_dry_run_receipt"))
        if previous_quant_dry_run_receipt.get("schema_version") == QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION:
            search_quant_projection_acceptance_dry_run_receipt = previous_quant_dry_run_receipt
            search_quant_projection_acceptance_dry_run_rows = [
                row
                for row in _as_list(previous_map.get("search_quant_projection_acceptance_dry_run_rows"))
                if isinstance(row, dict)
            ] or [row for row in _as_list(previous_quant_dry_run_receipt.get("rows")) if isinstance(row, dict)]
            search_quant_projection_credential_presence_rows = [
                row
                for row in _as_list(previous_map.get("search_quant_projection_credential_presence_rows"))
                if isinstance(row, dict)
            ]
    search_quant_projection_execution_request_receipt = _as_dict(
        snapshot_map.get("search_quant_projection_execution_request_receipt")
    )
    search_quant_projection_execution_request_rows = [
        row
        for row in _as_list(snapshot_map.get("search_quant_projection_execution_request_rows"))
        if isinstance(row, dict)
    ]
    if not search_quant_projection_execution_request_receipt:
        previous_quant_request_receipt = _as_dict(
            previous_map.get("search_quant_projection_execution_request_receipt")
        )
        if previous_quant_request_receipt.get("schema_version") == QUANT_PROJECTION_EXECUTION_REQUEST_SCHEMA_VERSION:
            search_quant_projection_execution_request_receipt = previous_quant_request_receipt
            search_quant_projection_execution_request_rows = [
                row
                for row in _as_list(previous_map.get("search_quant_projection_execution_request_rows"))
                if isinstance(row, dict)
            ] or [row for row in _as_list(previous_quant_request_receipt.get("rows")) if isinstance(row, dict)]
    search_quant_provider_model_acceptance_receipt = _as_dict(
        snapshot_map.get("search_quant_provider_model_acceptance_receipt")
    )
    search_quant_provider_model_acceptance_rows = [
        row
        for row in _as_list(snapshot_map.get("search_quant_provider_model_acceptance_rows"))
        if isinstance(row, dict)
    ]
    if not search_quant_provider_model_acceptance_receipt:
        previous_provider_model_receipt = _as_dict(
            previous_map.get("search_quant_provider_model_acceptance_receipt")
        )
        if (
            previous_provider_model_receipt.get("schema_version")
            == QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION
        ):
            search_quant_provider_model_acceptance_receipt = previous_provider_model_receipt
            search_quant_provider_model_acceptance_rows = [
                row
                for row in _as_list(previous_map.get("search_quant_provider_model_acceptance_rows"))
                if isinstance(row, dict)
            ] or [row for row in _as_list(previous_provider_model_receipt.get("rows")) if isinstance(row, dict)]
    provider_parity_dry_run_receipt = _as_dict(snapshot_map.get("provider_parity_dry_run_receipt"))
    provider_parity_dry_run_rows = [
        row for row in _as_list(snapshot_map.get("provider_parity_dry_run_rows")) if isinstance(row, dict)
    ]
    provider_parity_credential_presence_rows = [
        row for row in _as_list(snapshot_map.get("provider_parity_credential_presence_rows")) if isinstance(row, dict)
    ]
    if not provider_parity_dry_run_receipt:
        previous_provider_receipt = _as_dict(previous_map.get("provider_parity_dry_run_receipt"))
        if previous_provider_receipt.get("schema_version") == CANDIDATE_PROVIDER_PARITY_DRY_RUN_SCHEMA_VERSION:
            provider_parity_dry_run_receipt = previous_provider_receipt
            provider_parity_dry_run_rows = [
                row for row in _as_list(previous_map.get("provider_parity_dry_run_rows")) if isinstance(row, dict)
            ] or [row for row in _as_list(previous_provider_receipt.get("rows")) if isinstance(row, dict)]
            provider_parity_credential_presence_rows = [
                row
                for row in _as_list(previous_map.get("provider_parity_credential_presence_rows"))
                if isinstance(row, dict)
            ]
    provider_parity_execution_request_receipt = _as_dict(
        snapshot_map.get("provider_parity_execution_request_receipt")
    )
    provider_parity_execution_request_rows = [
        row for row in _as_list(snapshot_map.get("provider_parity_execution_request_rows")) if isinstance(row, dict)
    ]
    if not provider_parity_execution_request_receipt:
        previous_provider_request_receipt = _as_dict(previous_map.get("provider_parity_execution_request_receipt"))
        if (
            previous_provider_request_receipt.get("schema_version")
            == CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_SCHEMA_VERSION
        ):
            provider_parity_execution_request_receipt = previous_provider_request_receipt
            provider_parity_execution_request_rows = [
                row
                for row in _as_list(previous_map.get("provider_parity_execution_request_rows"))
                if isinstance(row, dict)
            ] or [row for row in _as_list(previous_provider_request_receipt.get("rows")) if isinstance(row, dict)]
    provider_parity_acceptance_receipt = _as_dict(snapshot_map.get("provider_parity_acceptance_receipt"))
    provider_parity_acceptance_rows = [
        row for row in _as_list(snapshot_map.get("provider_parity_acceptance_rows")) if isinstance(row, dict)
    ]
    if not provider_parity_acceptance_receipt:
        previous_provider_acceptance_receipt = _as_dict(previous_map.get("provider_parity_acceptance_receipt"))
        if (
            previous_provider_acceptance_receipt.get("schema_version")
            == CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_SCHEMA_VERSION
        ):
            provider_parity_acceptance_receipt = previous_provider_acceptance_receipt
            provider_parity_acceptance_rows = [
                row
                for row in _as_list(previous_map.get("provider_parity_acceptance_rows"))
                if isinstance(row, dict)
            ] or [row for row in _as_list(previous_provider_acceptance_receipt.get("rows")) if isinstance(row, dict)]
    counts["full_pool_local_execution_row_count"] = full_pool_local_execution_receipt["row_count"]
    counts["full_pool_local_execution_candidate_count"] = full_pool_local_execution_receipt["normalized_candidate_count"]
    counts["full_pool_local_execution_production_blocker_count"] = full_pool_local_execution_receipt[
        "production_blocker_count"
    ]
    counts["deep_scan_local_review_row_count"] = deep_scan_local_review_receipt["row_count"]
    counts["deep_scan_local_review_candidate_count"] = deep_scan_local_review_receipt["reviewed_candidate_count"]
    counts["deep_scan_local_review_production_blocker_count"] = deep_scan_local_review_receipt[
        "production_blocker_count"
    ]
    counts["search_quant_projection_row_count"] = search_quant_projection_receipt.get("row_count", 0)
    counts["search_quant_projection_production_blocker_count"] = search_quant_projection_receipt.get(
        "production_blocker_count", 0
    )
    counts["search_quant_projection_activation_row_count"] = search_quant_projection_activation_receipt.get("row_count", 0)
    counts["search_quant_projection_activation_blocker_count"] = search_quant_projection_activation_receipt.get(
        "production_blocker_count", 0
    )
    counts["search_quant_projection_acceptance_dry_run_row_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("row_count", 0)
    )
    counts["search_quant_projection_acceptance_dry_run_blocking_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("blocking_phase_count", 0)
    )
    counts["search_quant_projection_acceptance_credential_missing_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("credential_missing_provider_count", 0)
    )
    counts["search_quant_provider_model_acceptance_row_count"] = (
        search_quant_provider_model_acceptance_receipt.get("row_count", 0)
    )
    counts["search_quant_provider_model_acceptance_direct_evidence_verified"] = (
        search_quant_provider_model_acceptance_receipt.get("direct_evidence_verified") is True
    )
    counts["search_quant_provider_model_acceptance_provider_api_success_count"] = (
        search_quant_provider_model_acceptance_receipt.get("provider_api_success_count", 0)
    )
    counts["search_quant_provider_model_acceptance_production_blocker_count"] = (
        search_quant_provider_model_acceptance_receipt.get("production_blocker_count", 0)
    )
    counts["search_quant_projection_execution_request_row_count"] = (
        search_quant_projection_execution_request_receipt.get("row_count", 0)
    )
    counts["search_quant_projection_execution_request_local_blocker_count"] = (
        search_quant_projection_execution_request_receipt.get("local_blocker_count", 0)
    )
    counts["search_quant_projection_execution_request_production_blocker_count"] = (
        search_quant_projection_execution_request_receipt.get("production_blocker_count", 0)
    )
    counts["search_quant_projection_execution_request_ready"] = (
        search_quant_projection_execution_request_receipt.get("local_execution_request_ready") is True
    )
    counts["provider_parity_dry_run_row_count"] = provider_parity_dry_run_receipt.get("row_count", 0)
    counts["provider_parity_dry_run_blocking_count"] = provider_parity_dry_run_receipt.get("blocking_phase_count", 0)
    counts["provider_parity_credential_missing_count"] = provider_parity_dry_run_receipt.get(
        "credential_missing_provider_count", 0
    )
    counts["provider_parity_candidate_symbol_count"] = provider_parity_dry_run_receipt.get(
        "candidate_symbol_count", 0
    )
    counts["provider_parity_execution_request_row_count"] = provider_parity_execution_request_receipt.get(
        "row_count", 0
    )
    counts["provider_parity_execution_request_local_blocker_count"] = (
        provider_parity_execution_request_receipt.get("local_blocker_count", 0)
    )
    counts["provider_parity_execution_request_production_blocker_count"] = (
        provider_parity_execution_request_receipt.get("production_blocker_count", 0)
    )
    counts["provider_parity_execution_request_ready"] = (
        provider_parity_execution_request_receipt.get("local_execution_request_ready") is True
    )
    counts["provider_parity_acceptance_row_count"] = provider_parity_acceptance_receipt.get("row_count", 0)
    counts["provider_parity_acceptance_direct_evidence_verified"] = (
        provider_parity_acceptance_receipt.get("direct_evidence_verified") is True
    )
    counts["provider_parity_acceptance_provider_api_success_count"] = (
        provider_parity_acceptance_receipt.get("provider_api_success_count", 0)
    )
    counts["provider_parity_acceptance_production_blocker_count"] = (
        provider_parity_acceptance_receipt.get("production_blocker_count", 0)
    )
    full_pool_blocker_rows = _as_list(plan.get("blocker_rows"))
    deep_scan_blocker_rows = _as_list(deep_plan.get("blocker_rows"))
    scan_execution_summary = _scan_execution_summary(
        mode=mode,
        cache_source=cache_source,
        scan_mode=scan_mode,
        request_params_safe=request_params_safe or {},
        coverage=coverage,
        candidate_rows=candidate_rows,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
    )
    scan_acceptance_rows = _scan_acceptance_rows(
        scan_mode=scan_mode,
        coverage=coverage,
        candidate_rows=candidate_rows,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
    )
    fast_scan_runtime_budget_contract = _fast_scan_runtime_budget_contract(
        scan_mode=scan_mode,
        coverage=coverage,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
    )
    (
        candidate_browser_qa_runbook_contract,
        candidate_browser_qa_runbook_rows,
        candidate_browser_qa_matrix_rows,
    ) = _candidate_browser_qa_runbook_contract()
    candidate_browser_qa_evidence_summary, candidate_browser_qa_evidence_rows = _candidate_browser_qa_evidence_summary()
    previous_browser_review = _as_dict(previous_map.get("candidate_browser_qa_review_contract"))
    previous_browser_review_done = previous_browser_review.get("explicit_review_task_done") is True
    candidate_browser_qa_review_contract = _candidate_browser_qa_review_contract(
        candidate_browser_qa_evidence_summary,
        candidate_browser_qa_evidence_rows,
        explicit_review=previous_browser_review_done,
        task_id=str(previous_browser_review.get("task_id") or previous_map.get("task_id") or "")
        if previous_browser_review_done
        else None,
        reviewed_at=str(
            previous_browser_review.get("reviewed_at")
            or previous_map.get("candidate_browser_qa_review_completed_at")
            or ""
        )
        if previous_browser_review_done
        else None,
    )
    counts["fast_scan_runtime_budget_row_count"] = fast_scan_runtime_budget_contract["row_count"]
    counts["candidate_browser_qa_runbook_row_count"] = candidate_browser_qa_runbook_contract["row_count"]
    counts["candidate_browser_qa_matrix_count"] = candidate_browser_qa_runbook_contract["qa_matrix_count"]
    counts["candidate_browser_qa_blocking_phase_count"] = candidate_browser_qa_runbook_contract["blocking_phase_count"]
    counts["candidate_browser_qa_evidence_report_count"] = candidate_browser_qa_evidence_summary["candidate_report_count"]
    counts["candidate_browser_qa_evidence_row_count"] = candidate_browser_qa_evidence_summary["row_count"]
    counts["candidate_browser_qa_evidence_review_required_count"] = candidate_browser_qa_evidence_summary[
        "review_required_count"
    ]
    counts["candidate_browser_qa_visual_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_visual_qa_evidence_passed"
    ]
    counts["candidate_browser_qa_performance_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_browser_performance_evidence_passed"
    ]
    counts["candidate_browser_qa_review_blocking_count"] = candidate_browser_qa_review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = candidate_browser_qa_review_contract["local_browser_qa_review_ready"]
    fast_scan_readiness_rows = _fast_scan_readiness_rows(
        mode=mode,
        scan_mode=scan_mode,
        cache_source=cache_source,
        coverage=coverage,
        scan_execution_summary=scan_execution_summary,
        scan_acceptance_rows=scan_acceptance_rows,
        parity_inventory=parity_inventory,
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
        runtime_budget_contract=fast_scan_runtime_budget_contract,
    )
    fast_scan_readiness_audit = _fast_scan_readiness_audit(fast_scan_readiness_rows)
    result_delta_clarity_contract = _result_delta_clarity_contract(
        scan_mode=scan_mode,
        candidate_rows=candidate_rows,
        counts=counts,
        coverage=coverage,
        scan_execution_summary=scan_execution_summary,
        scan_acceptance_rows=scan_acceptance_rows,
        runtime_budget_contract=fast_scan_runtime_budget_contract,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
        previous_packet=previous_packet,
    )
    candidate_priority_explanation_contract = _candidate_priority_explanation_contract(
        candidate_rows,
        scan_mode=scan_mode,
        coverage=coverage,
    )
    if plan:
        counts["full_pool_plan_blocking_issue_count"] = plan.get("blocking_issue_count")
        counts["full_pool_plan_ready_signal_group_count"] = plan.get("ready_signal_group_count")
        counts["full_pool_plan_provider_gap_count"] = plan.get("provider_gap_count")
    if deep_plan:
        counts["deep_scan_plan_blocking_issue_count"] = deep_plan.get("blocking_issue_count")
        counts["deep_scan_plan_ready_signal_group_count"] = deep_plan.get("ready_signal_group_count")
        counts["deep_scan_plan_provider_gap_count"] = deep_plan.get("provider_gap_count")
        counts["deep_scan_plan_legacy_feature_gap_count"] = deep_plan.get("legacy_feature_gap_count")
    counts["fast_scan_readiness_blocker_count"] = fast_scan_readiness_audit["blocking_criterion_count"]
    counts["fast_scan_readiness_soft_blocker_count"] = fast_scan_readiness_audit["soft_blocker_count"]
    counts["fast_scan_readiness_row_count"] = fast_scan_readiness_audit["row_count"]
    counts["result_delta_clarity_visible_gap_count"] = result_delta_clarity_contract["visible_gap_count"]
    counts["result_delta_clarity_pending_count"] = result_delta_clarity_contract["production_pending_count"]
    counts["result_delta_clarity_row_count"] = result_delta_clarity_contract["row_count"]
    counts["result_delta_previous_candidate_count"] = result_delta_clarity_contract["previous_candidate_count"]
    counts["result_delta_added_count"] = result_delta_clarity_contract["candidate_added_count"]
    counts["result_delta_removed_count"] = result_delta_clarity_contract["candidate_removed_count"]
    counts["result_delta_rank_changed_count"] = result_delta_clarity_contract["candidate_rank_changed_count"]
    counts["result_delta_score_changed_count"] = result_delta_clarity_contract["candidate_score_changed_count"]
    counts["priority_explanation_row_count"] = candidate_priority_explanation_contract["row_count"]
    counts["priority_explanation_gap_count"] = candidate_priority_explanation_contract["explanation_gap_count"]
    counts["priority_explanation_data_gap_visible_count"] = candidate_priority_explanation_contract["data_gap_visible_count"]
    counts["priority_explanation_missing_score_count"] = candidate_priority_explanation_contract["missing_score_count"]

    if candidate_rows:
        status = "ready"
    elif radar_packet:
        status = "partial"
    elif snapshot:
        status = "cache_missing"
    else:
        status = "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_snapshot_hash": _snapshot_fingerprint(snapshot_map),
        "cache_source": cache_source,
        "scan_mode": scan_mode,
        "data_freshness": data_freshness_contract,
        "expected_trade_date": data_freshness_contract.get("expected_trade_date"),
        "expected_data_date": data_freshness_contract.get("expected_data_date"),
        "data_date": data_freshness_contract.get("data_date"),
        "latest_data_date": data_freshness_contract.get("latest_data_date"),
        "quick_scan_supported": True,
        "local_pool_scan_supported": True,
        "supported_local_scan_modes": sorted(SUPPORTED_LOCAL_SCAN_MODES),
        "source_packet_keys": [
            "radar_packet",
            "next_ticket_candidates",
            "candidate_execution_evidence_overview",
            "local_candidate_pool_audit",
        ],
        "summary": radar_packet.get("summary") or "候选雷达 cache 只读展示；无缓存时不自动扫描。",
        "manual_required_text": radar_packet.get("manual_required_text")
        or "下一票候选来自本地缓存或手动扫描结果；页面打开不会自动全市场扫描。",
        "counts": counts,
        "scan_coverage": coverage,
        "coverage_detail_summary": coverage["coverage_detail_summary"],
        "scan_execution_summary": scan_execution_summary,
        "scan_acceptance_rows": scan_acceptance_rows,
        "fast_scan_runtime_budget_contract": fast_scan_runtime_budget_contract,
        "fast_scan_runtime_budget_rows": fast_scan_runtime_budget_contract["rows"],
        "candidate_browser_qa_runbook_contract": candidate_browser_qa_runbook_contract,
        "candidate_browser_qa_runbook_rows": candidate_browser_qa_runbook_rows,
        "candidate_browser_qa_matrix_rows": candidate_browser_qa_matrix_rows,
        "candidate_browser_qa_evidence_summary": candidate_browser_qa_evidence_summary,
        "candidate_browser_qa_evidence_rows": candidate_browser_qa_evidence_rows,
        "candidate_browser_qa_review_contract": candidate_browser_qa_review_contract,
        "candidate_browser_qa_review_rows": candidate_browser_qa_review_contract["rows"],
        "fast_scan_readiness_audit": fast_scan_readiness_audit,
        "fast_scan_readiness_rows": fast_scan_readiness_rows,
        "result_delta_clarity_contract": result_delta_clarity_contract,
        "result_delta_clarity_rows": result_delta_clarity_contract["rows"],
        "previous_cache_diff_rows": result_delta_clarity_contract["previous_cache_diff_rows"],
        "candidate_priority_explanation_contract": candidate_priority_explanation_contract,
        "candidate_priority_explanation_rows": candidate_priority_explanation_contract["rows"],
        "provider_coverage_rows": coverage["provider_coverage_rows"],
        "degraded_mode_rows": coverage["degraded_mode_rows"],
        "local_candidate_pool_audit": dict(local_pool_audit or _as_dict(snapshot_map.get("local_candidate_pool_audit"))),
        "local_candidate_pool_skipped_rows": list(local_pool_skipped_rows or _as_list(snapshot_map.get("local_candidate_pool_skipped_rows"))),
        "legacy_signal_group_rows": coverage["legacy_signal_group_rows"],
        "legacy_parity_inventory": parity_inventory,
        "legacy_parity_rows": legacy_parity_rows,
        "legacy_output_contract_rows": legacy_output_contract_rows,
        "legacy_parity_acceptance_receipt": legacy_parity_acceptance_receipt,
        "legacy_parity_acceptance_rows": legacy_parity_acceptance_rows,
        "scan_mode_status_rows": [dict(row) for row in SCAN_MODE_STATUS_ROWS],
        "full_pool_scan_plan": plan,
        "full_pool_local_execution_receipt": full_pool_local_execution_receipt,
        "full_pool_local_execution_rows": full_pool_local_execution_rows,
        "full_pool_plan_stage_rows": _as_list(plan.get("stage_rows")),
        "full_pool_plan_filter_rows": _as_list(plan.get("filter_rows")),
        "full_pool_required_signal_rows": _as_list(plan.get("required_signal_rows")),
        "full_pool_blocker_rows": full_pool_blocker_rows,
        "deep_scan_plan": deep_plan,
        "deep_scan_local_review_receipt": deep_scan_local_review_receipt,
        "deep_scan_local_review_rows": deep_scan_local_review_rows,
        "search_quant_projection_receipt": search_quant_projection_receipt,
        "search_quant_projection_rows": search_quant_projection_rows,
        "search_quant_projection_activation_receipt": search_quant_projection_activation_receipt,
        "search_quant_projection_activation_rows": search_quant_projection_activation_rows,
        "search_quant_projection_acceptance_dry_run_receipt": search_quant_projection_acceptance_dry_run_receipt,
        "search_quant_projection_acceptance_dry_run_rows": search_quant_projection_acceptance_dry_run_rows,
        "search_quant_projection_credential_presence_rows": search_quant_projection_credential_presence_rows,
        "search_quant_projection_execution_request_receipt": search_quant_projection_execution_request_receipt,
        "search_quant_projection_execution_request_rows": search_quant_projection_execution_request_rows,
        "search_quant_provider_model_acceptance_receipt": search_quant_provider_model_acceptance_receipt,
        "search_quant_provider_model_acceptance_rows": search_quant_provider_model_acceptance_rows,
        "provider_parity_dry_run_receipt": provider_parity_dry_run_receipt,
        "provider_parity_dry_run_rows": provider_parity_dry_run_rows,
        "provider_parity_credential_presence_rows": provider_parity_credential_presence_rows,
        "provider_parity_execution_request_receipt": provider_parity_execution_request_receipt,
        "provider_parity_execution_request_rows": provider_parity_execution_request_rows,
        "provider_parity_acceptance_receipt": provider_parity_acceptance_receipt,
        "provider_parity_acceptance_rows": provider_parity_acceptance_rows,
        "deep_scan_stage_rows": _as_list(deep_plan.get("stage_rows")),
        "deep_scan_parity_rows": _as_list(deep_plan.get("parity_rows")),
        "deep_scan_required_signal_rows": _as_list(deep_plan.get("required_signal_rows")),
        "deep_scan_blocker_rows": deep_scan_blocker_rows,
        "skipped_reason_rows": coverage["skipped_reason_rows"],
        "freshness_state": coverage["freshness_state"],
        "candidate_rows": candidate_rows,
        "candidates": candidates[:10],
        "excluded_candidates": excluded_candidates,
        "candidate_execution_evidence_overview": _as_dict(snapshot_map.get("candidate_execution_evidence_overview")),
        "evidence_recovery_actions": evidence_recovery_actions,
        "old_workspace_packet_bridge": _as_dict(snapshot_map.get("old_workspace_packet_bridge")),
        "risk_alerts": _as_dict(snapshot_map.get("risk_alerts")),
        "radar_packet": radar_packet,
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_scan_market": True,
            "quick_scan_reads_cache_only": True,
            "local_pool_scan_reads_local_input_only": scan_mode in LOCAL_POOL_SCAN_MODES,
            "watchlist_scan_reads_local_input_only": scan_mode == "watchlist_scan",
            "custom_pool_scan_reads_local_input_only": scan_mode == "custom_pool_scan",
            "quick_scan_preserves_legacy_signal_groups": True,
            "missing_legacy_groups_are_reported": True,
            "provider_gaps_are_reported": True,
            "missing_provider_data_is_not_silently_dropped": True,
            "stale_inputs_are_research_only": True,
            "degraded_modes_are_visible": True,
            "full_pool_scan_requires_future_worker": True,
            "full_pool_plan_is_not_full_pool_scan": True,
            "full_pool_plan_writes_no_candidates": True,
            "full_pool_plan_provider_refresh_executed": False,
            "full_pool_local_execution_is_button_gated": scan_mode == "full_pool_local_scan",
            "full_pool_local_execution_is_not_provider_backed_acceptance": True,
            "full_pool_local_execution_does_not_refresh_provider": True,
            "deep_scan_plan_is_not_deep_scan": True,
            "deep_scan_plan_writes_no_new_candidates": True,
            "deep_scan_plan_provider_refresh_executed": False,
            "deep_scan_plan_deepseek_called": False,
            "deep_scan_feature_loss_gaps_visible": True,
            "deep_scan_local_review_is_button_gated": scan_mode == "deep_scan_local_review",
            "deep_scan_local_review_is_not_deep_scan_done": True,
            "deep_scan_local_review_does_not_call_deepseek": True,
            "deep_scan_local_review_does_not_refresh_provider": True,
            "search_quant_projection_is_button_gated": scan_mode == QUANT_PROJECTION_SCAN_MODE,
            "search_quant_projection_is_not_trade_signal": True,
            "search_quant_projection_provider_model_pending": bool(search_quant_projection_receipt),
            "search_quant_projection_does_not_call_provider_or_model": True,
            "search_quant_projection_activation_receipt_is_local": bool(search_quant_projection_activation_receipt),
            "search_quant_projection_activation_blocks_production": bool(search_quant_projection_activation_receipt),
            "search_quant_projection_requires_tushare_deepseek_ledgers": bool(search_quant_projection_activation_receipt),
            "search_quant_projection_acceptance_dry_run_is_button_gated": bool(
                search_quant_projection_acceptance_dry_run_receipt
            ),
            "search_quant_projection_acceptance_dry_run_is_local": bool(
                search_quant_projection_acceptance_dry_run_receipt
            ),
            "search_quant_projection_acceptance_dry_run_does_not_call_provider_or_model": True,
            "search_quant_projection_acceptance_dry_run_is_not_production_completion": True,
            "search_quant_projection_execution_request_is_button_gated": bool(
                search_quant_projection_execution_request_receipt
            ),
            "search_quant_projection_execution_request_is_local": bool(
                search_quant_projection_execution_request_receipt
            ),
            "search_quant_projection_execution_request_does_not_call_provider_or_model": True,
            "search_quant_projection_execution_request_is_not_production_completion": True,
            "provider_parity_dry_run_is_button_gated": bool(provider_parity_dry_run_receipt),
            "provider_parity_dry_run_is_local": bool(provider_parity_dry_run_receipt),
            "provider_parity_dry_run_does_not_call_provider_or_model": True,
            "provider_parity_dry_run_is_not_production_replacement": True,
            "provider_parity_dry_run_requires_worker_browser_ledgers": bool(provider_parity_dry_run_receipt),
            "provider_parity_execution_request_is_button_gated": bool(provider_parity_execution_request_receipt),
            "provider_parity_execution_request_is_local": bool(provider_parity_execution_request_receipt),
            "provider_parity_execution_request_does_not_call_provider_or_model": True,
            "provider_parity_execution_request_is_not_provider_backed_acceptance": True,
            "provider_parity_execution_request_is_not_production_replacement": True,
            "provider_parity_acceptance_is_button_gated": bool(provider_parity_acceptance_receipt),
            "provider_parity_acceptance_calls_provider_only_from_post_task": bool(provider_parity_acceptance_receipt),
            "provider_parity_acceptance_get_cache_calls_provider": False,
            "provider_parity_acceptance_deepseek_skipped": (
                provider_parity_acceptance_receipt.get("deepseek_skipped_by_request") is True
            ),
            "provider_parity_acceptance_is_not_production_replacement": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "candidate_is_not_buy_instruction": True,
            "post_task_required_for_scan": True,
            "fast_scan_runtime_budget_contract_visible": True,
            "candidate_browser_qa_runbook_contract_is_local": True,
            "candidate_browser_qa_runbook_ready": candidate_browser_qa_runbook_contract["local_runbook_ready"],
            "candidate_browser_qa_is_not_visual_qa": True,
            "candidate_browser_qa_is_not_production_replacement": True,
            "candidate_browser_qa_evidence_reads_local_artifact_only": True,
            "candidate_browser_qa_evidence_does_not_open_browser": True,
            "candidate_browser_qa_evidence_does_not_write_artifacts": True,
            "candidate_browser_qa_evidence_is_not_production_replacement": True,
            "candidate_browser_qa_evidence_found": candidate_browser_qa_evidence_summary["local_browser_qa_evidence_found"],
            "candidate_browser_qa_review_is_button_gated": True,
            "candidate_browser_qa_review_does_not_open_browser": True,
            "candidate_browser_qa_review_is_not_production_replacement": True,
            "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
            "large_universe_requires_worker": coverage["coverage_detail_summary"]["large_universe_requires_worker"],
            "fast_scan_readiness_audit_is_local": True,
            "fast_scan_readiness_is_not_full_replacement": True,
            "result_delta_clarity_contract_is_local": True,
            "result_delta_clarity_previous_cache_diff_done": bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_previous_cache_diff_is_local": bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_is_not_previous_cache_diff": not bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_is_not_browser_visual_qa": True,
            "candidate_priority_explanation_contract_is_local": True,
            "candidate_priority_explanation_uses_existing_rank_only": True,
            "candidate_priority_explanation_uses_existing_score_only": True,
            "candidate_priority_explanation_is_not_trade_signal": True,
            "legacy_parity_acceptance_receipt_is_local": True,
            "legacy_parity_acceptance_is_not_production_replacement": True,
            "legacy_parity_acceptance_requires_provider_worker_browser_evidence": True,
        },
        "call_ledger": [
            _candidate_call_ledger_row(
                api="local_candidate_radar_cache",
                source_snapshot="command_center_latest.json",
                row_count=len(candidate_rows),
                call_status="cache_read" if snapshot else "cache_missing",
                request_params_safe=request_params_safe or {},
            )
        ]
        + legacy_parity_acceptance_receipt["call_ledger"],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/candidate-radar/cache 只读展示下一票雷达缓存；不会自动全市场扫描。",
            "POST /api/candidate-radar/scan-quick 只扫描本地缓存并记录覆盖缺口；不会调用外部源。",
            "候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
            "provider 阻断、stale 输入、缺失 provider 数据和降级模式会作为 coverage gap 展示，不会在页面渲染时补数。",
        ],
    }
    if not candidate_rows:
        packet["warnings"].append("当前没有可展示候选；3.0 cache 页不会自动刷新或扫描。")
    packet = _preserve_candidate_radar_persisted_receipts(packet, previous_map)
    packet = _attach_quick_scan_receipt_contract(packet)
    task_pipeline_contract, task_pipeline_rows = _fast_scan_task_pipeline_contract(packet)
    counts = dict(_as_dict(packet.get("counts")))
    counts["fast_scan_task_pipeline_row_count"] = task_pipeline_contract["row_count"]
    counts["fast_scan_task_pipeline_local_blocker_count"] = task_pipeline_contract["local_blocker_count"]
    counts["fast_scan_task_pipeline_production_blocker_count"] = task_pipeline_contract["production_blocker_count"]
    packet["counts"] = counts
    policy = dict(_as_dict(packet.get("policy")))
    policy["fast_scan_task_pipeline_contract_is_local"] = True
    policy["fast_scan_task_pipeline_nonblocking_ui_contract_ready"] = task_pipeline_contract["local_task_pipeline_ready"]
    policy["fast_scan_task_pipeline_is_not_async_worker_execution"] = True
    policy["fast_scan_task_pipeline_does_not_call_provider_or_model"] = True
    policy["fast_scan_task_pipeline_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["fast_scan_task_pipeline_contract"] = task_pipeline_contract
    packet["fast_scan_task_pipeline_rows"] = task_pipeline_rows
    packet = _attach_no_feature_loss_acceptance_contract(packet)
    return _json_safe(packet)


def _read_persisted_packet() -> dict[str, Any] | None:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(PACKET_KEY)
    except Exception:
        return None
    return packet if isinstance(packet, dict) else None


def _cache_view_from_persisted(packet: Mapping[str, Any]) -> dict[str, Any]:
    row_count = len(_as_list(packet.get("candidate_rows")))
    persisted_scan_mode = str(packet.get("scan_mode") or "local_scan")
    candidate_browser_qa_evidence_summary, candidate_browser_qa_evidence_rows = _candidate_browser_qa_evidence_summary()
    persisted_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    explicit_review_done = persisted_review.get("explicit_review_task_done") is True
    candidate_browser_qa_review_contract = _candidate_browser_qa_review_contract(
        candidate_browser_qa_evidence_summary,
        candidate_browser_qa_evidence_rows,
        explicit_review=explicit_review_done,
        task_id=str(persisted_review.get("task_id") or packet.get("task_id") or "") if explicit_review_done else None,
        reviewed_at=str(persisted_review.get("reviewed_at") or packet.get("candidate_browser_qa_review_completed_at") or "")
        if explicit_review_done
        else None,
    )
    cache_row = _candidate_call_ledger_row(
        api="local_candidate_radar_cache",
        source_snapshot="sqlite_meta_candidate_radar_packet",
        row_count=row_count,
        call_status=f"cache_read_persisted_{persisted_scan_mode}",
    )
    view = dict(_json_safe(packet))
    existing_ledger = _as_list(view.get("call_ledger"))
    view["loaded_at"] = _now_iso()
    view["cache_only"] = True
    view["read_only"] = True
    view["cache_source"] = "sqlite_meta"
    view["call_ledger"] = [cache_row] + [row for row in existing_ledger if isinstance(row, dict)]
    if not isinstance(view.get("legacy_parity_acceptance_receipt"), dict):
        parity_receipt, parity_acceptance_rows = _legacy_parity_acceptance_receipt(
            parity_inventory=_as_dict(view.get("legacy_parity_inventory")),
            parity_rows=[row for row in _as_list(view.get("legacy_parity_rows")) if isinstance(row, dict)],
            output_contract_rows=[
                row for row in _as_list(view.get("legacy_output_contract_rows")) if isinstance(row, dict)
            ],
        )
        view["legacy_parity_acceptance_receipt"] = parity_receipt
        view["legacy_parity_acceptance_rows"] = parity_acceptance_rows
        view["call_ledger"] = view["call_ledger"] + parity_receipt["call_ledger"]
    if not isinstance(view.get("full_pool_local_execution_receipt"), dict):
        full_pool_local_receipt, full_pool_local_rows = _full_pool_local_execution_receipt(
            scan_mode=persisted_scan_mode,
            local_pool_audit=_as_dict(view.get("local_candidate_pool_audit")),
            candidate_rows=[row for row in _as_list(view.get("candidate_rows")) if isinstance(row, dict)],
            full_pool_scan_plan=_as_dict(view.get("full_pool_scan_plan")),
            coverage={
                "freshness_state": _as_dict(view.get("freshness_state")),
                "coverage_detail_summary": _as_dict(view.get("coverage_detail_summary")),
            },
        )
        view["full_pool_local_execution_receipt"] = full_pool_local_receipt
        view["full_pool_local_execution_rows"] = full_pool_local_rows
    if not isinstance(view.get("deep_scan_local_review_receipt"), dict):
        deep_scan_local_receipt, deep_scan_local_rows = _deep_scan_local_review_receipt(
            scan_mode=persisted_scan_mode,
            candidate_rows=[row for row in _as_list(view.get("candidate_rows")) if isinstance(row, dict)],
            deep_scan_plan=_as_dict(view.get("deep_scan_plan")),
            legacy_parity_acceptance=_as_dict(view.get("legacy_parity_acceptance_receipt")),
            coverage={
                "freshness_state": _as_dict(view.get("freshness_state")),
                "coverage_detail_summary": _as_dict(view.get("coverage_detail_summary")),
            },
        )
        view["deep_scan_local_review_receipt"] = deep_scan_local_receipt
        view["deep_scan_local_review_rows"] = deep_scan_local_rows
    view["candidate_browser_qa_evidence_summary"] = candidate_browser_qa_evidence_summary
    view["candidate_browser_qa_evidence_rows"] = candidate_browser_qa_evidence_rows
    view["candidate_browser_qa_review_contract"] = candidate_browser_qa_review_contract
    view["candidate_browser_qa_review_rows"] = candidate_browser_qa_review_contract["rows"]
    counts = _as_dict(view.get("counts"))
    counts["candidate_browser_qa_evidence_report_count"] = candidate_browser_qa_evidence_summary["candidate_report_count"]
    counts["candidate_browser_qa_evidence_row_count"] = candidate_browser_qa_evidence_summary["row_count"]
    counts["candidate_browser_qa_evidence_review_required_count"] = candidate_browser_qa_evidence_summary[
        "review_required_count"
    ]
    counts["candidate_browser_qa_visual_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_visual_qa_evidence_passed"
    ]
    counts["candidate_browser_qa_performance_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_browser_performance_evidence_passed"
    ]
    counts["candidate_browser_qa_review_blocking_count"] = candidate_browser_qa_review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = candidate_browser_qa_review_contract["local_browser_qa_review_ready"]
    parity_receipt = _as_dict(view.get("legacy_parity_acceptance_receipt"))
    counts["legacy_parity_acceptance_row_count"] = parity_receipt.get("receipt_row_count")
    counts["legacy_parity_acceptance_production_blocker_count"] = parity_receipt.get("production_blocker_count")
    counts["legacy_parity_acceptance_ready_count"] = parity_receipt.get("production_ready_count")
    full_pool_local_receipt = _as_dict(view.get("full_pool_local_execution_receipt"))
    counts["full_pool_local_execution_row_count"] = full_pool_local_receipt.get("row_count")
    counts["full_pool_local_execution_candidate_count"] = full_pool_local_receipt.get("normalized_candidate_count")
    counts["full_pool_local_execution_production_blocker_count"] = full_pool_local_receipt.get(
        "production_blocker_count"
    )
    deep_scan_local_receipt = _as_dict(view.get("deep_scan_local_review_receipt"))
    counts["deep_scan_local_review_row_count"] = deep_scan_local_receipt.get("row_count")
    counts["deep_scan_local_review_candidate_count"] = deep_scan_local_receipt.get("reviewed_candidate_count")
    counts["deep_scan_local_review_production_blocker_count"] = deep_scan_local_receipt.get("production_blocker_count")
    search_quant_projection_receipt = _as_dict(view.get("search_quant_projection_receipt"))
    search_quant_projection_activation_receipt, search_quant_projection_activation_rows = _quant_projection_activation_receipt(
        search_quant_projection_receipt
    )
    if search_quant_projection_activation_receipt:
        view["search_quant_projection_activation_receipt"] = search_quant_projection_activation_receipt
        view["search_quant_projection_activation_rows"] = search_quant_projection_activation_rows
    counts["search_quant_projection_row_count"] = search_quant_projection_receipt.get("row_count", 0)
    counts["search_quant_projection_production_blocker_count"] = search_quant_projection_receipt.get(
        "production_blocker_count", 0
    )
    counts["search_quant_projection_activation_row_count"] = search_quant_projection_activation_receipt.get("row_count", 0)
    counts["search_quant_projection_activation_blocker_count"] = search_quant_projection_activation_receipt.get(
        "production_blocker_count", 0
    )
    search_quant_projection_acceptance_dry_run_receipt = _as_dict(
        view.get("search_quant_projection_acceptance_dry_run_receipt")
    )
    counts["search_quant_projection_acceptance_dry_run_row_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("row_count", 0)
    )
    counts["search_quant_projection_acceptance_dry_run_blocking_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("blocking_phase_count", 0)
    )
    counts["search_quant_projection_acceptance_credential_missing_count"] = (
        search_quant_projection_acceptance_dry_run_receipt.get("credential_missing_provider_count", 0)
    )
    search_quant_provider_model_acceptance_receipt = _as_dict(
        view.get("search_quant_provider_model_acceptance_receipt")
    )
    counts["search_quant_provider_model_acceptance_row_count"] = (
        search_quant_provider_model_acceptance_receipt.get("row_count", 0)
    )
    counts["search_quant_provider_model_acceptance_direct_evidence_verified"] = (
        search_quant_provider_model_acceptance_receipt.get("direct_evidence_verified") is True
    )
    counts["search_quant_provider_model_acceptance_provider_api_success_count"] = (
        search_quant_provider_model_acceptance_receipt.get("provider_api_success_count", 0)
    )
    counts["search_quant_provider_model_acceptance_production_blocker_count"] = (
        search_quant_provider_model_acceptance_receipt.get("production_blocker_count", 0)
    )
    provider_parity_dry_run_receipt = _as_dict(view.get("provider_parity_dry_run_receipt"))
    counts["provider_parity_dry_run_row_count"] = provider_parity_dry_run_receipt.get("row_count", 0)
    counts["provider_parity_dry_run_blocking_count"] = provider_parity_dry_run_receipt.get("blocking_phase_count", 0)
    counts["provider_parity_credential_missing_count"] = provider_parity_dry_run_receipt.get(
        "credential_missing_provider_count", 0
    )
    counts["provider_parity_candidate_symbol_count"] = provider_parity_dry_run_receipt.get("candidate_symbol_count", 0)
    provider_parity_acceptance_receipt = _as_dict(view.get("provider_parity_acceptance_receipt"))
    counts["provider_parity_acceptance_row_count"] = provider_parity_acceptance_receipt.get("row_count", 0)
    counts["provider_parity_acceptance_direct_evidence_verified"] = (
        provider_parity_acceptance_receipt.get("direct_evidence_verified") is True
    )
    counts["provider_parity_acceptance_provider_api_success_count"] = (
        provider_parity_acceptance_receipt.get("provider_api_success_count", 0)
    )
    counts["provider_parity_acceptance_production_blocker_count"] = (
        provider_parity_acceptance_receipt.get("production_blocker_count", 0)
    )
    view["counts"] = counts
    policy = _as_dict(view.get("policy"))
    policy["candidate_browser_qa_evidence_reads_local_artifact_only"] = True
    policy["candidate_browser_qa_evidence_does_not_open_browser"] = True
    policy["candidate_browser_qa_evidence_does_not_write_artifacts"] = True
    policy["candidate_browser_qa_evidence_is_not_production_replacement"] = True
    policy["candidate_browser_qa_evidence_found"] = candidate_browser_qa_evidence_summary["local_browser_qa_evidence_found"]
    policy["candidate_browser_qa_review_is_button_gated"] = True
    policy["candidate_browser_qa_review_does_not_open_browser"] = True
    policy["candidate_browser_qa_review_is_not_production_replacement"] = True
    policy["legacy_parity_acceptance_receipt_is_local"] = True
    policy["legacy_parity_acceptance_is_not_production_replacement"] = True
    policy["legacy_parity_acceptance_requires_provider_worker_browser_evidence"] = True
    policy["full_pool_local_execution_is_button_gated"] = persisted_scan_mode == "full_pool_local_scan"
    policy["full_pool_local_execution_is_not_provider_backed_acceptance"] = True
    policy["full_pool_local_execution_does_not_refresh_provider"] = True
    policy["deep_scan_local_review_is_button_gated"] = persisted_scan_mode == "deep_scan_local_review"
    policy["deep_scan_local_review_is_not_deep_scan_done"] = True
    policy["deep_scan_local_review_does_not_call_deepseek"] = True
    policy["deep_scan_local_review_does_not_refresh_provider"] = True
    policy["search_quant_projection_is_button_gated"] = persisted_scan_mode == QUANT_PROJECTION_SCAN_MODE
    policy["search_quant_projection_is_not_trade_signal"] = True
    policy["search_quant_projection_provider_model_pending"] = bool(search_quant_projection_receipt)
    policy["search_quant_projection_does_not_call_provider_or_model"] = True
    policy["search_quant_projection_activation_receipt_is_local"] = bool(search_quant_projection_activation_receipt)
    policy["search_quant_projection_activation_blocks_production"] = bool(search_quant_projection_activation_receipt)
    policy["search_quant_projection_requires_tushare_deepseek_ledgers"] = bool(search_quant_projection_activation_receipt)
    policy["search_quant_projection_acceptance_dry_run_is_button_gated"] = bool(
        search_quant_projection_acceptance_dry_run_receipt
    )
    policy["search_quant_projection_acceptance_dry_run_is_local"] = bool(
        search_quant_projection_acceptance_dry_run_receipt
    )
    policy["search_quant_projection_acceptance_dry_run_does_not_call_provider_or_model"] = True
    policy["search_quant_projection_acceptance_dry_run_is_not_production_completion"] = True
    policy["search_quant_provider_model_acceptance_is_button_gated"] = bool(
        search_quant_provider_model_acceptance_receipt
    )
    policy["search_quant_provider_model_acceptance_calls_provider_only_from_post_task"] = bool(
        search_quant_provider_model_acceptance_receipt
    )
    policy["search_quant_provider_model_acceptance_get_cache_calls_provider"] = False
    policy["search_quant_provider_model_acceptance_deepseek_skipped"] = (
        search_quant_provider_model_acceptance_receipt.get("deepseek_skipped_by_request") is True
    )
    policy["search_quant_provider_model_acceptance_is_not_production_completion"] = True
    policy["provider_parity_dry_run_is_button_gated"] = bool(provider_parity_dry_run_receipt)
    policy["provider_parity_dry_run_is_local"] = bool(provider_parity_dry_run_receipt)
    policy["provider_parity_dry_run_does_not_call_provider_or_model"] = True
    policy["provider_parity_dry_run_is_not_production_replacement"] = True
    policy["provider_parity_dry_run_requires_worker_browser_ledgers"] = bool(provider_parity_dry_run_receipt)
    policy["provider_parity_acceptance_is_button_gated"] = bool(provider_parity_acceptance_receipt)
    policy["provider_parity_acceptance_calls_provider_only_from_post_task"] = bool(provider_parity_acceptance_receipt)
    policy["provider_parity_acceptance_get_cache_calls_provider"] = False
    policy["provider_parity_acceptance_deepseek_skipped"] = (
        provider_parity_acceptance_receipt.get("deepseek_skipped_by_request") is True
    )
    policy["provider_parity_acceptance_is_not_production_replacement"] = True
    view["policy"] = policy
    warnings = _as_list(view.get("warnings"))
    first_warning = "GET /api/candidate-radar/cache 只读展示已持久化的 local scan 结果；不会自动全市场扫描。"
    view["warnings"] = [first_warning] + [str(item) for item in warnings if item != first_warning]
    view["external_calls_triggered"] = False
    view["tushare_called"] = False
    view["deepseek_called"] = False
    view["github_called"] = False
    view["does_not_execute_trades"] = True
    view["does_not_modify_strategy_action"] = True
    view["contains_secret"] = False
    view = _attach_quick_scan_receipt_contract(view)
    task_pipeline_contract, task_pipeline_rows = _fast_scan_task_pipeline_contract(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["fast_scan_task_pipeline_row_count"] = task_pipeline_contract["row_count"]
    counts["fast_scan_task_pipeline_local_blocker_count"] = task_pipeline_contract["local_blocker_count"]
    counts["fast_scan_task_pipeline_production_blocker_count"] = task_pipeline_contract["production_blocker_count"]
    view["counts"] = counts
    policy = dict(_as_dict(view.get("policy")))
    policy["fast_scan_task_pipeline_contract_is_local"] = True
    policy["fast_scan_task_pipeline_nonblocking_ui_contract_ready"] = task_pipeline_contract["local_task_pipeline_ready"]
    policy["fast_scan_task_pipeline_is_not_async_worker_execution"] = True
    policy["fast_scan_task_pipeline_does_not_call_provider_or_model"] = True
    policy["fast_scan_task_pipeline_is_not_production_replacement"] = True
    view["policy"] = policy
    view["fast_scan_task_pipeline_contract"] = task_pipeline_contract
    view["fast_scan_task_pipeline_rows"] = task_pipeline_rows
    view = _attach_no_feature_loss_acceptance_contract(view)
    view = _attach_candidate_radar_durable_evidence_recipe(view)
    view = _attach_candidate_radar_production_stage_scope_manifest(view)
    return _json_safe(view)


def read_candidate_radar_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    snapshot_hash = _snapshot_fingerprint(snapshot_map)
    persisted = _read_persisted_packet()
    if persisted and (
        persisted.get("source_snapshot_hash") == snapshot_hash
        or str(persisted.get("scan_mode") or "") in PERSISTED_TASK_SCAN_MODES
    ):
        return _cache_view_from_persisted(persisted)
    return _build_candidate_radar_packet(
        snapshot,
        mode="cache_only",
        cache_source="snapshot",
        scan_mode="cache_only",
        previous_packet=persisted,
    )


def run_candidate_quick_scan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_quick_scan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quick_scan_queued",
        warnings=[
            "候选雷达 quick scan 只读取本地 snapshot/cache；不会全市场扫描、不会调用 Tushare、DeepSeek 或 GitHub。",
            "候选不是买入指令；扫描结果不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_snapshot",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    requested_scan_mode = str(payload_safe.get("scan_mode") or "quick_cache_scan")
    scan_mode = requested_scan_mode if requested_scan_mode in SUPPORTED_LOCAL_SCAN_MODES else "quick_cache_scan"
    request_params_safe = {
        "requested_scan_mode": requested_scan_mode,
        "scan_mode": scan_mode,
        "unsupported_scan_mode_fallback": requested_scan_mode != scan_mode,
        "universe_mode": payload_safe.get("universe_mode")
        or ("local_watchlist" if scan_mode == "watchlist_scan" else "manual_input" if scan_mode == "custom_pool_scan" else "cache_snapshot"),
        "external_sources_allowed": False,
        "local_pool_scan": scan_mode in LOCAL_POOL_SCAN_MODES,
    }
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    scan_snapshot: Mapping[str, Any] = snapshot
    local_pool_audit: dict[str, Any] = {}
    local_pool_skipped_rows: list[dict[str, Any]] = []
    if scan_mode in LOCAL_POOL_SCAN_MODES:
        scan_snapshot, local_pool_audit, local_pool_skipped_rows = _snapshot_with_local_candidate_pool(
            snapshot_map,
            payload_safe,
            scan_mode,
        )
        request_params_safe["candidate_pool_source"] = local_pool_audit.get("input_source")
        request_params_safe["input_candidate_count"] = local_pool_audit.get("input_candidate_count")
        request_params_safe["normalized_candidate_count"] = local_pool_audit.get("normalized_candidate_count")
    packet = _build_candidate_radar_packet(
        scan_snapshot,
        mode=scan_mode,
        cache_source=f"{scan_mode}_task",
        scan_mode=scan_mode,
        request_params_safe=request_params_safe,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        previous_packet=previous_packet,
    )
    task_scan_label = "quick_scan" if scan_mode == "quick_cache_scan" else scan_mode
    ledger_api = "local_candidate_radar_quick_scan" if scan_mode == "quick_cache_scan" else f"local_candidate_radar_{scan_mode}"
    quick_ledger = _candidate_call_ledger_row(
        api=ledger_api,
        source_snapshot="command_center_latest.json",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=f"{task_scan_label}_completed" if scan_snapshot else f"{task_scan_label}_cache_missing",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["quick_scan_completed_at"] = _now_iso()
    packet["local_scan_completed_at"] = packet["quick_scan_completed_at"]
    packet["call_ledger"] = [quick_ledger]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        quick_ledger["call_status"] = "quick_scan_storage_write_failed"
        quick_ledger["error_message_safe"] = "candidate_radar_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quick_scan_storage_write_failed",
            error_message_safe="candidate_radar_sqlite_write_failed",
            call_ledger=[quick_ledger],
            warning="candidate_radar_quick_scan_failed_no_external_call",
        ) or task

    final_warning = f"candidate_radar_{task_scan_label}_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_warning = f"candidate_radar_{task_scan_label}_completed_no_candidates_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=f"candidate_radar_{task_scan_label}_completed",
        call_ledger=[quick_ledger],
        warning=final_warning,
    ) or task


def run_candidate_quant_projection_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_quant_projection",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quant_projection_queued",
        warnings=[
            "搜票量化推演当前只生成本地回执；不会调用 Tushare、DeepSeek 或 GitHub。",
            "量化推演是 research-only 补证路线，不生成买卖建议、不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_local_search_quant_projection_receipt",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    projection_snapshot, projection_receipt, projection_rows = _snapshot_with_quant_projection(snapshot_map, payload_safe)
    request_params_safe = {
        "scan_mode": QUANT_PROJECTION_SCAN_MODE,
        "symbol": projection_receipt.get("symbol"),
        "raw_input_safe": projection_receipt.get("raw_input_safe"),
        "symbol_valid": projection_receipt.get("symbol_valid") is True,
        "include_tushare_requested": payload_safe.get("include_tushare") is True,
        "include_deepseek_requested": payload_safe.get("include_deepseek") is True,
        "selected_light_apis": projection_receipt.get("selected_light_apis") or [],
        "external_sources_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_quant_projection_complete": False,
    }
    packet = _build_candidate_radar_packet(
        projection_snapshot,
        mode=QUANT_PROJECTION_SCAN_MODE,
        cache_source="search_quant_projection_task",
        scan_mode=QUANT_PROJECTION_SCAN_MODE,
        request_params_safe=request_params_safe,
        previous_packet=previous_packet,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_quant_projection",
        source_snapshot="local_search_payload",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=str(projection_receipt.get("status") or "quant_projection_local_receipt_ready_provider_model_pending"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["search_quant_projection_completed_at"] = _now_iso()
    packet["search_quant_projection_receipt"] = projection_receipt
    packet["search_quant_projection_rows"] = projection_rows
    packet["call_ledger"] = [ledger] + [
        row for row in _as_list(projection_receipt.get("call_ledger")) if isinstance(row, dict)
    ]
    packet["warnings"] = [
        "搜票量化推演已写入本地回执；真实 Tushare / Factor / Next Session / DeepSeek / ECharts 证据仍待后续显式任务补齐。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "搜票量化推演" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "quant_projection_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_quant_projection_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quant_projection_storage_write_failed",
            error_message_safe="candidate_radar_quant_projection_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_quant_projection_failed_no_external_call",
        ) or task

    final_step = "candidate_radar_quant_projection_ready"
    final_warning = "candidate_radar_quant_projection_ready_no_external_call"
    if projection_receipt.get("symbol_valid") is not True:
        final_step = "candidate_radar_quant_projection_blocked_invalid_symbol"
        final_warning = "candidate_radar_quant_projection_blocked_invalid_symbol_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning=final_warning,
    ) or task


def run_candidate_quant_projection_acceptance_dry_run_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        QUANT_PROJECTION_ACCEPTANCE_DRY_RUN_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quant_projection_acceptance_dry_run_queued",
        warnings=[
            "搜票量化推演联动验收 dry-run 只做本地预检；不会调用 Tushare、DeepSeek 或 GitHub。",
            "dry-run 只检查服务端凭据存在性，不读取、不返回 token/key 值或 env key 名。",
            "dry-run 不执行真实交易，不修改 strategy action，不刷新 Factor/Next/ECharts。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.2,
        current_step="building_local_quant_projection_acceptance_dry_run",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    projection_snapshot, projection_receipt, projection_rows = _snapshot_with_quant_projection(snapshot_map, payload_safe)
    activation_receipt, activation_rows = _quant_projection_activation_receipt(projection_receipt)
    dry_run_receipt, dry_run_rows, credential_rows = _build_quant_projection_acceptance_dry_run(
        quant_receipt=projection_receipt,
        activation_receipt=activation_receipt,
        payload_safe=payload_safe,
    )
    projection_snapshot["search_quant_projection_acceptance_dry_run_receipt"] = dry_run_receipt
    projection_snapshot["search_quant_projection_acceptance_dry_run_rows"] = dry_run_rows
    projection_snapshot["search_quant_projection_credential_presence_rows"] = credential_rows
    request_params_safe = {
        "scan_mode": QUANT_PROJECTION_SCAN_MODE,
        "symbol": projection_receipt.get("symbol"),
        "symbol_valid": projection_receipt.get("symbol_valid") is True,
        "user_approved": dry_run_receipt.get("user_approved") is True,
        "include_tushare": dry_run_receipt.get("include_tushare") is True,
        "include_deepseek": dry_run_receipt.get("include_deepseek") is True,
        "selected_apis": dry_run_receipt.get("selected_apis") or [],
        "ignored_apis": dry_run_receipt.get("ignored_apis") or [],
        "credential_required_provider_count": dry_run_receipt.get("credential_required_provider_count", 0),
        "credential_present_provider_count": dry_run_receipt.get("credential_present_provider_count", 0),
        "credential_missing_provider_count": dry_run_receipt.get("credential_missing_provider_count", 0),
        "acceptance_scope_hash_short": dry_run_receipt.get("acceptance_scope_hash_short"),
        "external_sources_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_quant_projection_complete": False,
    }
    packet = _build_candidate_radar_packet(
        projection_snapshot,
        mode=QUANT_PROJECTION_SCAN_MODE,
        cache_source="search_quant_projection_acceptance_dry_run_task",
        scan_mode=QUANT_PROJECTION_SCAN_MODE,
        request_params_safe=request_params_safe,
        previous_packet=previous_packet,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_quant_projection_acceptance_dry_run",
        source_snapshot="local_search_payload",
        row_count=len(dry_run_rows),
        call_status=str(dry_run_receipt.get("status") or "quant_projection_acceptance_dry_run_recorded_no_external_call"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["search_quant_projection_acceptance_dry_run_completed_at"] = _now_iso()
    packet["search_quant_projection_receipt"] = projection_receipt
    packet["search_quant_projection_rows"] = projection_rows
    packet["search_quant_projection_activation_receipt"] = activation_receipt
    packet["search_quant_projection_activation_rows"] = activation_rows
    packet["search_quant_projection_acceptance_dry_run_receipt"] = dry_run_receipt
    packet["search_quant_projection_acceptance_dry_run_rows"] = dry_run_rows
    packet["search_quant_projection_credential_presence_rows"] = credential_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["search_quant_projection_acceptance_dry_run_row_count"] = dry_run_receipt.get("row_count", 0)
    packet_counts["search_quant_projection_acceptance_dry_run_blocking_count"] = dry_run_receipt.get(
        "blocking_phase_count", 0
    )
    packet_counts["search_quant_projection_acceptance_credential_missing_count"] = dry_run_receipt.get(
        "credential_missing_provider_count", 0
    )
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["search_quant_projection_acceptance_dry_run_is_button_gated"] = True
    packet_policy["search_quant_projection_acceptance_dry_run_is_local"] = True
    packet_policy["search_quant_projection_acceptance_dry_run_does_not_call_provider_or_model"] = True
    packet_policy["search_quant_projection_acceptance_dry_run_is_not_production_completion"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [ledger] + [
        row for row in _as_list(projection_receipt.get("call_ledger")) if isinstance(row, dict)
    ]
    packet["warnings"] = [
        "搜票量化推演联动验收 dry-run 已写入本地预检；真实 Tushare / DeepSeek / Factor / Next / ECharts 仍未执行。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "搜票量化推演联动验收" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "quant_projection_acceptance_dry_run_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_quant_projection_acceptance_dry_run_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quant_projection_acceptance_dry_run_storage_write_failed",
            error_message_safe="candidate_radar_quant_projection_acceptance_dry_run_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_quant_projection_acceptance_dry_run_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_quant_projection_acceptance_dry_run_ready",
        call_ledger=[ledger],
        warning="candidate_radar_quant_projection_acceptance_dry_run_ready_no_external_call",
    ) or task


def run_candidate_quant_projection_execution_request_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        QUANT_PROJECTION_EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quant_projection_execution_request_queued",
        warnings=[
            "搜票量化推演 provider/model execution request 只生成本地申请票据；不会调用 Tushare、DeepSeek 或 GitHub。",
            "request ticket 不创建 provider/model 任务，不刷新 Factor/Next/ECharts，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_quant_projection_execution_request",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    receipt, receipt_rows = _candidate_radar_quant_projection_execution_request(
        packet,
        payload_safe=payload_safe,
        explicit_request=True,
        task_id=str(task["task_id"]),
    )
    request_params_safe = {
        "operator_approved": receipt.get("operator_approved"),
        "symbol": receipt.get("symbol"),
        "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_matches_latest": receipt.get(
            "requested_acceptance_scope_hash_matches_latest"
        ),
        "local_execution_request_ready": receipt.get("local_execution_request_ready"),
        "selected_apis": receipt.get("selected_apis") or [],
        "include_tushare": receipt.get("include_tushare") is True,
        "include_deepseek": receipt.get("include_deepseek") is True,
        "external_sources_allowed": False,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_quant_projection_execution_request",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "quant_projection_execution_request_recorded"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["search_quant_projection_execution_request_completed_at"] = _now_iso()
    packet["search_quant_projection_execution_request_receipt"] = receipt
    packet["search_quant_projection_execution_request_rows"] = receipt_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["search_quant_projection_execution_request_row_count"] = len(receipt_rows)
    packet_counts["search_quant_projection_execution_request_local_blocker_count"] = receipt.get(
        "local_blocker_count", 0
    )
    packet_counts["search_quant_projection_execution_request_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    packet_counts["search_quant_projection_execution_request_ready"] = (
        receipt.get("local_execution_request_ready") is True
    )
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["search_quant_projection_execution_request_is_button_gated"] = True
    packet_policy["search_quant_projection_execution_request_is_local"] = True
    packet_policy["search_quant_projection_execution_request_does_not_call_provider_or_model"] = True
    packet_policy["search_quant_projection_execution_request_is_not_production_completion"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "搜票量化推演 provider/model execution request 已写入本地申请票据；真实 Tushare / DeepSeek / Factor / Next / ECharts 仍未执行。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "provider/model execution request" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "quant_projection_execution_request_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_quant_projection_execution_request_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quant_projection_execution_request_storage_write_failed",
            error_message_safe="candidate_radar_quant_projection_execution_request_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_quant_projection_execution_request_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_quant_projection_execution_request_ready",
        call_ledger=[ledger],
        warning="candidate_radar_quant_projection_execution_request_ready_no_external_call",
    ) or task


def _quant_projection_provider_model_acceptance_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _candidate_radar_quant_projection_provider_model_acceptance_receipt(
    packet: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any],
    provider_task: Mapping[str, Any] | None,
    explicit_request: bool,
    task_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    operator_approved = _coerce_bool(
        payload_safe.get("operator_approved") or payload_safe.get("user_approved") or payload_safe.get("approved"),
        False,
    )
    requested_scope_hash = _safe_text(
        payload_safe.get("acceptance_scope_hash") or payload_safe.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(quant_request.get("acceptance_scope_hash") or "", limit=128)
    scope_hash_matches = bool(requested_scope_hash and expected_scope_hash and requested_scope_hash == expected_scope_hash)
    execution_request_ready = quant_request.get("local_execution_request_ready") is True
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), False)
    selected_apis = [
        str(api)
        for api in _as_list(quant_request.get("selected_apis"))
        if str(api) in QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS
    ] or list(QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS)
    provider_ledger = [
        row for row in _as_list((provider_task or {}).get("call_ledger")) if isinstance(row, dict)
    ]
    success_rows = [row for row in provider_ledger if row.get("call_status") == "success"]
    failed_rows = [
        row
        for row in provider_ledger
        if row.get("call_status") == "failed" or str(row.get("call_status") or "").startswith("blocked_")
    ]
    provider_executed = bool(provider_task)
    provider_evidence_done = bool(
        provider_executed
        and provider_ledger
        and len(success_rows) == len(selected_apis)
        and not failed_rows
        and all(row.get("tushare_called") is True for row in provider_ledger)
    )
    rows = [
        _quant_projection_provider_model_acceptance_row(
            "explicit_post_provider_model_acceptance_done",
            "passed_explicit_post" if explicit_request else "blocked_missing_explicit_post",
            passed=explicit_request,
            production_blocker=not explicit_request,
            evidence=f"task_id={task_id}",
            next_action="Use only POST /api/candidate-radar/quant-projection-provider-model-acceptance.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "operator_approval_recorded",
            "passed_operator_approved" if operator_approved else "blocked_operator_approval_required",
            passed=operator_approved,
            production_blocker=not operator_approved,
            evidence=f"operator_approved={operator_approved}",
            next_action="Require explicit operator approval before provider execution.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "execution_request_ready",
            "passed_execution_request_ready" if execution_request_ready else "blocked_execution_request_missing",
            passed=execution_request_ready,
            production_blocker=not execution_request_ready,
            evidence=f"quant_request={quant_request.get('status') or 'missing'}",
            next_action="Create a scope-bound execution request before provider acceptance.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "acceptance_scope_hash_bound",
            "passed_scope_hash_bound" if scope_hash_matches else "blocked_scope_hash_mismatch_or_missing",
            passed=scope_hash_matches,
            production_blocker=not scope_hash_matches,
            evidence=(
                f"requested={requested_scope_hash[:16] if requested_scope_hash else 'missing'}; "
                f"expected={expected_scope_hash[:16] if expected_scope_hash else 'missing'}"
            ),
            next_action="Bind provider execution to the latest quant projection execution-request scope hash.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "deepseek_model_ledger_policy",
            "passed_deepseek_skipped_by_request" if not include_deepseek else "blocked_deepseek_not_enabled_this_cycle",
            passed=not include_deepseek,
            production_blocker=include_deepseek,
            evidence=f"include_deepseek={include_deepseek}; model_execution_implemented=false",
            next_action="Run DeepSeek benchmark/model ledger in a separate explicitly approved cycle.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "tushare_light_provider_call_ledger",
            "passed_tushare_light_provider_ledger" if provider_evidence_done else "blocked_tushare_provider_ledger_missing_or_failed",
            passed=provider_evidence_done,
            production_blocker=not provider_evidence_done,
            evidence=f"api_success={len(success_rows)}/{len(selected_apis)}; selected_apis={selected_apis}",
            next_action="Collect safe Tushare call ledger for trade_cal/daily/daily_basic/moneyflow.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "factor_next_echarts_refresh_still_pending",
            "passed_refresh_pending_research_only",
            passed=True,
            production_blocker=True,
            evidence="Provider evidence is captured, but Factor Quant Hub, Next Session, and ECharts refresh are separate evidence.",
            next_action="Refresh local research caches only after provider evidence review.",
        ),
        _quant_projection_provider_model_acceptance_row(
            "no_trade_action_secret_boundary",
            "passed_no_trade_action_secret_boundary",
            passed=True,
            production_blocker=False,
            evidence="No trade execution, no strategy action mutation, no credential value exposure.",
            next_action="Keep Candidate Radar output research-only.",
        ),
    ]
    blocking_rows = [row for row in rows if row.get("production_blocker")]
    if include_deepseek:
        status = "search_quant_provider_model_acceptance_blocked_deepseek_not_enabled_this_cycle"
    elif not execution_request_ready:
        status = "search_quant_provider_model_acceptance_blocked_execution_request_required"
    elif not scope_hash_matches:
        status = "search_quant_provider_model_acceptance_blocked_scope_hash_mismatch"
    elif not provider_evidence_done:
        status = "search_quant_provider_model_acceptance_blocked_provider_ledger_missing_or_failed"
    else:
        status = "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped"
    receipt = {
        "schema_version": QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_search_quant_provider_model_acceptance_tushare_light_deepseek_skipped",
        "mode": "button_gated_provider_model_acceptance",
        "ltg": "LTG-13/LTG-02/LTG-07",
        "route": QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
        "task_type": QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_TASK_TYPE,
        "task_id": task_id,
        "symbol": quant_request.get("symbol") or "",
        "selected_apis": selected_apis,
        "acceptance_scope_hash": expected_scope_hash,
        "acceptance_scope_hash_short": expected_scope_hash[:16] if expected_scope_hash else "",
        "requested_acceptance_scope_hash_matches_latest": scope_hash_matches,
        "operator_approved": operator_approved,
        "execution_request_ready": execution_request_ready,
        "provider_execution_implemented": provider_executed,
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": provider_evidence_done,
        "deepseek_model_ledger_evidence_done": False,
        "deepseek_skipped_by_request": not include_deepseek,
        "direct_evidence_verified": provider_evidence_done and not include_deepseek,
        "provider_call_ledger": provider_ledger,
        "provider_api_call_count": len(provider_ledger),
        "provider_api_success_count": len(success_rows),
        "provider_api_failed_count": len(failed_rows),
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "browser_nonblocking_evidence_complete": False,
        "production_quant_projection_complete": False,
        "production_radar_replacement_complete": False,
        "production_blocker_count": len(blocking_rows),
        "production_blockers": [row["criterion"] for row in blocking_rows],
        "external_calls_triggered_by_task": provider_executed,
        "tushare_called_by_task": provider_executed,
        "deepseek_called": False,
        "github_called": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "rows": rows,
    }
    return receipt, rows


def run_candidate_quant_projection_provider_model_acceptance_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        QUANT_PROJECTION_PROVIDER_MODEL_ACCEPTANCE_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quant_projection_provider_model_acceptance_queued",
        warnings=[
            "搜票量化推演 provider/model acceptance 是显式 POST 任务；本轮只允许 Tushare light provider ledger。",
            "DeepSeek 默认跳过；该任务不刷新 Factor/Next/ECharts，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    quant_request = _as_dict(packet.get("search_quant_projection_execution_request_receipt"))
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), False)
    selected_apis = [
        str(api)
        for api in _as_list(quant_request.get("selected_apis"))
        if str(api) in QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS
    ] or list(QUANT_PROJECTION_ACCEPTANCE_ALLOWED_APIS)
    today = _dt.date.today()
    start_date = _safe_text(payload_safe.get("start_date") or (today - _dt.timedelta(days=14)).strftime("%Y%m%d"))
    end_date = _safe_text(payload_safe.get("end_date") or today.strftime("%Y%m%d"))
    provider_task: Mapping[str, Any] | None = None
    requested_scope_hash = _safe_text(
        payload_safe.get("acceptance_scope_hash") or payload_safe.get("scope_hash") or "",
        limit=128,
    )
    can_call_provider = bool(
        not include_deepseek
        and quant_request.get("local_execution_request_ready") is True
        and requested_scope_hash
        and requested_scope_hash == _safe_text(quant_request.get("acceptance_scope_hash") or "", limit=128)
    )
    if can_call_provider:
        task_service.update_task_status(
            task["task_id"],
            status="running",
            progress=0.45,
            current_step="calling_tushare_light_provider_for_quant_projection",
        )
        provider_task = tushare_task_service.run_tushare_refresh_task(
            {
                "apis": selected_apis,
                "symbol": quant_request.get("symbol") or "",
                "ts_code": quant_request.get("symbol") or "",
                "start_date": start_date,
                "end_date": end_date,
                "operator": "candidate_radar_quant_projection_provider_model_acceptance",
            },
            task_type="candidate_radar_quant_projection_tushare_light_provider",
            output_packet_key="command_center_candidate_radar_quant_projection_tushare_light_packet",
        )
    receipt, receipt_rows = _candidate_radar_quant_projection_provider_model_acceptance_receipt(
        packet,
        payload_safe=payload_safe,
        provider_task=provider_task,
        explicit_request=True,
        task_id=str(task["task_id"]),
    )
    request_params_safe = {
        "symbol": receipt.get("symbol"),
        "selected_apis": selected_apis,
        "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_matches_latest": receipt.get(
            "requested_acceptance_scope_hash_matches_latest"
        ),
        "operator_approved": receipt.get("operator_approved"),
        "include_deepseek": include_deepseek,
        "provider_execution_implemented": receipt.get("provider_execution_implemented"),
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": receipt.get("tushare_call_ledger_evidence_done"),
        "deepseek_model_ledger_evidence_done": False,
        "production_quant_projection_complete": False,
    }
    local_ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_quant_projection_provider_model_acceptance",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status")),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "quant_projection_provider_model_acceptance"
    packet["search_quant_provider_model_acceptance_completed_at"] = _now_iso()
    packet["search_quant_provider_model_acceptance_receipt"] = receipt
    packet["search_quant_provider_model_acceptance_rows"] = receipt_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["search_quant_provider_model_acceptance_row_count"] = len(receipt_rows)
    packet_counts["search_quant_provider_model_acceptance_direct_evidence_verified"] = (
        receipt.get("direct_evidence_verified") is True
    )
    packet_counts["search_quant_provider_model_acceptance_provider_api_success_count"] = receipt.get(
        "provider_api_success_count", 0
    )
    packet_counts["search_quant_provider_model_acceptance_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["search_quant_provider_model_acceptance_is_button_gated"] = True
    packet_policy["search_quant_provider_model_acceptance_calls_provider_only_from_post_task"] = True
    packet_policy["search_quant_provider_model_acceptance_get_cache_calls_provider"] = False
    packet_policy["search_quant_provider_model_acceptance_deepseek_skipped"] = receipt.get(
        "deepseek_skipped_by_request"
    )
    packet_policy["search_quant_provider_model_acceptance_is_not_production_completion"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [local_ledger]
    packet["warnings"] = [
        "搜票量化推演 provider/model acceptance 已记录 Tushare light provider ledger；DeepSeek/Factor/Next/ECharts/production promotion 仍是后续证据。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "provider/model acceptance" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        local_ledger["call_status"] = "quant_projection_provider_model_acceptance_storage_write_failed"
        local_ledger["error_message_safe"] = "candidate_radar_quant_projection_provider_model_acceptance_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quant_projection_provider_model_acceptance_storage_write_failed",
            error_message_safe="candidate_radar_quant_projection_provider_model_acceptance_sqlite_write_failed",
            call_ledger=[local_ledger],
            warning="candidate_radar_quant_projection_provider_model_acceptance_storage_failed",
        ) or task

    provider_ledger = [
        row for row in _as_list(receipt.get("provider_call_ledger")) if isinstance(row, dict)
    ]
    task_ledger = [local_ledger] + provider_ledger
    final_status = "success" if receipt.get("direct_evidence_verified") is True else "failed"
    return task_service.update_task_status(
        task["task_id"],
        status=final_status,
        progress=1.0,
        current_step=str(receipt.get("status")),
        call_ledger=task_ledger,
        warning="candidate_radar_quant_projection_provider_model_acceptance_recorded",
        error_message_safe="" if final_status == "success" else str(receipt.get("status")),
    ) or task


def run_candidate_provider_parity_dry_run_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PROVIDER_PARITY_DRY_RUN_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_provider_parity_dry_run_queued",
        warnings=[
            "下一票雷达 provider parity dry-run 只做本地预检；不会调用 Tushare、DeepSeek 或 GitHub。",
            "dry-run 只检查服务端凭据存在性，不读取、不返回 token/key 值或 env key 名。",
            "dry-run 不执行全池/深扫 worker，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_local_candidate_provider_parity_dry_run",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    request_params_safe = {
        "scan_mode": "provider_parity_dry_run",
        "user_approved": _coerce_bool(payload_safe.get("user_approved") or payload_safe.get("approved"), False),
        "include_tushare": _coerce_bool(payload_safe.get("include_tushare"), True),
        "include_deepseek": _coerce_bool(payload_safe.get("include_deepseek"), True),
        "external_sources_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_radar_replacement_complete": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="provider_parity_dry_run",
        cache_source="provider_parity_dry_run_task",
        scan_mode="provider_parity_dry_run",
        request_params_safe=request_params_safe,
        previous_packet=previous_packet,
    )
    receipt, receipt_rows, credential_rows = _build_candidate_provider_parity_dry_run(
        packet=packet,
        payload_safe=payload_safe,
    )
    request_params_safe.update(
        {
            "selected_signal_groups": receipt.get("selected_signal_groups") or [],
            "selected_apis": receipt.get("selected_apis") or [],
            "candidate_symbol_count": receipt.get("candidate_symbol_count", 0),
            "provider_coverage_gap_count": receipt.get("provider_coverage_gap_count", 0),
            "credential_required_provider_count": receipt.get("credential_required_provider_count", 0),
            "credential_present_provider_count": receipt.get("credential_present_provider_count", 0),
            "credential_missing_provider_count": receipt.get("credential_missing_provider_count", 0),
            "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        }
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_provider_parity_dry_run",
        source_snapshot="local_candidate_radar_packet_and_payload",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_provider_parity_dry_run_recorded_no_external_call"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["provider_parity_dry_run_completed_at"] = _now_iso()
    packet["provider_parity_dry_run_receipt"] = receipt
    packet["provider_parity_dry_run_rows"] = receipt_rows
    packet["provider_parity_credential_presence_rows"] = credential_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["provider_parity_dry_run_row_count"] = receipt.get("row_count", 0)
    packet_counts["provider_parity_dry_run_blocking_count"] = receipt.get("blocking_phase_count", 0)
    packet_counts["provider_parity_credential_missing_count"] = receipt.get("credential_missing_provider_count", 0)
    packet_counts["provider_parity_candidate_symbol_count"] = receipt.get("candidate_symbol_count", 0)
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["provider_parity_dry_run_is_button_gated"] = True
    packet_policy["provider_parity_dry_run_is_local"] = True
    packet_policy["provider_parity_dry_run_does_not_call_provider_or_model"] = True
    packet_policy["provider_parity_dry_run_is_not_production_replacement"] = True
    packet_policy["provider_parity_dry_run_requires_worker_browser_ledgers"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 provider parity dry-run 已写入本地预检；真实 Tushare / DeepSeek / full-pool / deep-scan / browser promotion 仍未执行。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "provider parity dry-run" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "provider_parity_dry_run_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_provider_parity_dry_run_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_provider_parity_dry_run_storage_write_failed",
            error_message_safe="candidate_radar_provider_parity_dry_run_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_provider_parity_dry_run_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_provider_parity_dry_run_ready",
        call_ledger=[ledger],
        warning="candidate_radar_provider_parity_dry_run_ready_no_external_call",
    ) or task



def run_candidate_provider_parity_execution_request_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PROVIDER_PARITY_EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_provider_parity_execution_request_queued",
        warnings=[
            "下一票雷达 provider parity execution request 只生成本地申请票据；不会调用 Tushare、DeepSeek 或 GitHub。",
            "request ticket 不创建 provider/model 任务，不刷新雷达证据，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_provider_parity_execution_request",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    receipt, receipt_rows = _candidate_radar_provider_parity_execution_request(
        packet,
        payload_safe=payload_safe,
        explicit_request=True,
        task_id=str(task["task_id"]),
    )
    request_params_safe = {
        "operator_approved": receipt.get("operator_approved"),
        "candidate_symbol_count": receipt.get("candidate_symbol_count"),
        "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_matches_latest": receipt.get(
            "requested_acceptance_scope_hash_matches_latest"
        ),
        "local_execution_request_ready": receipt.get("local_execution_request_ready"),
        "selected_apis": receipt.get("selected_apis") or [],
        "selected_signal_groups": receipt.get("selected_signal_groups") or [],
        "include_tushare": receipt.get("include_tushare") is True,
        "include_deepseek": receipt.get("include_deepseek") is True,
        "external_sources_allowed": False,
        "provider_task_created": False,
        "provider_task_executed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_provider_parity_execution_request",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_provider_parity_execution_request_recorded"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["provider_parity_execution_request_completed_at"] = _now_iso()
    packet["provider_parity_execution_request_receipt"] = receipt
    packet["provider_parity_execution_request_rows"] = receipt_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["provider_parity_execution_request_row_count"] = len(receipt_rows)
    packet_counts["provider_parity_execution_request_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    packet_counts["provider_parity_execution_request_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    packet_counts["provider_parity_execution_request_ready"] = receipt.get("local_execution_request_ready") is True
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["provider_parity_execution_request_is_button_gated"] = True
    packet_policy["provider_parity_execution_request_is_local"] = True
    packet_policy["provider_parity_execution_request_does_not_call_provider_or_model"] = True
    packet_policy["provider_parity_execution_request_is_not_provider_backed_acceptance"] = True
    packet_policy["provider_parity_execution_request_is_not_production_replacement"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 provider parity execution request 已写入本地申请票据；真实 Tushare / DeepSeek / provider parity 仍未执行。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "provider parity execution request" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "provider_parity_execution_request_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_provider_parity_execution_request_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_provider_parity_execution_request_storage_write_failed",
            error_message_safe="candidate_radar_provider_parity_execution_request_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_provider_parity_execution_request_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_provider_parity_execution_request_ready",
        call_ledger=[ledger],
        warning="candidate_radar_provider_parity_execution_request_ready_no_external_call",
    ) or task


def run_candidate_provider_parity_acceptance_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PROVIDER_PARITY_ACCEPTANCE_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_provider_parity_acceptance_queued",
        warnings=[
            "下一票雷达 provider parity acceptance 是显式 POST 任务；本轮只允许 Tushare light provider ledger。",
            "DeepSeek 默认跳过；该任务不启动 worker，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    execution_request = _as_dict(packet.get("provider_parity_execution_request_receipt"))
    include_deepseek = _coerce_bool(payload_safe.get("include_deepseek"), False)
    requested_scope_hash = _safe_text(
        payload_safe.get("acceptance_scope_hash") or payload_safe.get("scope_hash") or "",
        limit=128,
    )
    expected_scope_hash = _safe_text(execution_request.get("acceptance_scope_hash") or "", limit=128)
    max_candidates = max(1, min(3, int(payload_safe.get("max_candidates") or 1)))
    max_apis = max(1, min(8, int(payload_safe.get("max_apis") or 5)))
    candidate_symbols = [
        str(symbol)
        for symbol in _as_list(execution_request.get("candidate_symbols"))
        if str(symbol).strip()
    ][:max_candidates]
    executed_apis, skipped_apis = _candidate_provider_parity_acceptance_apis(
        _as_list(execution_request.get("selected_apis")),
        max_apis=max_apis,
    )
    today = _dt.date.today()
    start_date = _safe_text(payload_safe.get("start_date") or (today - _dt.timedelta(days=14)).strftime("%Y%m%d"))
    end_date = _safe_text(payload_safe.get("end_date") or today.strftime("%Y%m%d"))
    can_call_provider = bool(
        not include_deepseek
        and execution_request.get("local_execution_request_ready") is True
        and requested_scope_hash
        and requested_scope_hash == expected_scope_hash
        and candidate_symbols
        and executed_apis
    )
    provider_tasks: list[Mapping[str, Any]] = []
    if can_call_provider:
        task_service.update_task_status(
            task["task_id"],
            status="running",
            progress=0.45,
            current_step="calling_tushare_light_provider_for_candidate_provider_parity",
        )
        for symbol in candidate_symbols:
            provider_task = tushare_task_service.run_tushare_refresh_task(
                {
                    "apis": executed_apis,
                    "symbol": symbol,
                    "ts_code": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "trade_date": end_date,
                    "operator": "candidate_radar_provider_parity_acceptance",
                },
                task_type="candidate_radar_provider_parity_tushare_light_provider",
                output_packet_key="command_center_candidate_radar_provider_parity_tushare_light_packet",
            )
            provider_tasks.append(provider_task)
    receipt, receipt_rows, evidence_artifact = _candidate_provider_parity_acceptance_receipt(
        packet,
        payload_safe=payload_safe,
        provider_tasks=provider_tasks,
        executed_apis=executed_apis,
        skipped_apis=skipped_apis,
        explicit_request=True,
        task_id=str(task["task_id"]),
    )
    request_params_safe = {
        "operator_approved": receipt.get("operator_approved"),
        "candidate_symbol_count": receipt.get("candidate_symbol_count"),
        "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_matches_latest": receipt.get(
            "requested_acceptance_scope_hash_matches_latest"
        ),
        "execution_request_ready": receipt.get("execution_request_ready"),
        "selected_apis": executed_apis,
        "skipped_apis": skipped_apis,
        "include_deepseek": include_deepseek,
        "provider_execution_implemented": receipt.get("provider_execution_implemented"),
        "model_execution_implemented": False,
        "tushare_call_ledger_evidence_done": receipt.get("tushare_call_ledger_evidence_done"),
        "provider_backed_acceptance_done": False,
        "production_radar_replacement_complete": False,
    }
    local_ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_provider_parity_acceptance",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status")),
        request_params_safe=request_params_safe,
    )
    if receipt.get("direct_evidence_verified") is True:
        try:
            CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CANDIDATE_PROVIDER_PARITY_TUSHARE_LIGHT_EVIDENCE_PATH.write_text(
                json.dumps(_safe_value(evidence_artifact), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            local_ledger["call_status"] = "provider_parity_acceptance_artifact_write_failed"
            local_ledger["error_message_safe"] = "candidate_radar_provider_parity_tushare_light_artifact_write_failed"
            return task_service.update_task_status(
                task["task_id"],
                status="failed",
                progress=1.0,
                current_step="candidate_radar_provider_parity_acceptance_artifact_write_failed",
                error_message_safe="candidate_radar_provider_parity_tushare_light_artifact_write_failed",
                call_ledger=[local_ledger],
                warning="candidate_radar_provider_parity_acceptance_artifact_failed",
            ) or task
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "provider_parity_acceptance"
    packet["provider_parity_acceptance_completed_at"] = _now_iso()
    packet["provider_parity_acceptance_receipt"] = receipt
    packet["provider_parity_acceptance_rows"] = receipt_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["provider_parity_acceptance_row_count"] = len(receipt_rows)
    packet_counts["provider_parity_acceptance_direct_evidence_verified"] = (
        receipt.get("direct_evidence_verified") is True
    )
    packet_counts["provider_parity_acceptance_provider_api_success_count"] = receipt.get(
        "provider_api_success_count", 0
    )
    packet_counts["provider_parity_acceptance_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["provider_parity_acceptance_is_button_gated"] = True
    packet_policy["provider_parity_acceptance_calls_provider_only_from_post_task"] = True
    packet_policy["provider_parity_acceptance_get_cache_calls_provider"] = False
    packet_policy["provider_parity_acceptance_deepseek_skipped"] = receipt.get("deepseek_skipped_by_request")
    packet_policy["provider_parity_acceptance_is_not_production_replacement"] = True
    packet["policy"] = packet_policy
    provider_ledger = [row for row in _as_list(receipt.get("provider_call_ledger")) if isinstance(row, dict)]
    packet["call_ledger"] = [local_ledger] + provider_ledger
    packet["warnings"] = [
        "下一票雷达 provider parity acceptance 已记录 Tushare light provider ledger；DeepSeek/worker/browser/legacy promotion 仍是后续证据。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "provider parity acceptance" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        local_ledger["call_status"] = "provider_parity_acceptance_storage_write_failed"
        local_ledger["error_message_safe"] = "candidate_radar_provider_parity_acceptance_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_provider_parity_acceptance_storage_write_failed",
            error_message_safe="candidate_radar_provider_parity_acceptance_sqlite_write_failed",
            call_ledger=[local_ledger] + provider_ledger,
            warning="candidate_radar_provider_parity_acceptance_storage_failed",
        ) or task
    final_status = "success" if receipt.get("direct_evidence_verified") is True else "failed"
    return task_service.update_task_status(
        task["task_id"],
        status=final_status,
        progress=1.0,
        current_step=str(receipt.get("status")),
        call_ledger=[local_ledger] + provider_ledger,
        warning="candidate_radar_provider_parity_acceptance_recorded",
        error_message_safe="" if final_status == "success" else str(receipt.get("status")),
    ) or task


def run_candidate_worker_execution_request_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_WORKER_EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_worker_execution_request_queued",
        warnings=[
            "下一票雷达 worker execution request 只生成本地申请票据；不会启动 worker、不会扫描全市场。",
            "request ticket 不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_worker_execution_request",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    receipt, receipt_rows = _candidate_radar_worker_execution_request(
        packet,
        payload_safe=payload_safe,
        explicit_request=True,
        task_id=str(task["task_id"]),
    )
    request_params_safe = {
        "operator_approved": receipt.get("operator_approved"),
        "worker_execution_scope_hash_short": receipt.get("worker_execution_scope_hash_short"),
        "requested_worker_execution_scope_hash_matches_latest": receipt.get(
            "requested_worker_execution_scope_hash_matches_latest"
        ),
        "local_execution_request_ready": receipt.get("local_execution_request_ready"),
        "provider_parity_scope_ticket_visible": receipt.get("provider_parity_scope_ticket_visible"),
        "quant_projection_scope_ticket_visible": receipt.get("quant_projection_scope_ticket_visible"),
        "external_sources_allowed": False,
        "worker_started": False,
        "worker_task_created": False,
        "worker_task_executed": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_worker_execution_request",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_radar_worker_execution_request_recorded"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["candidate_radar_worker_execution_request_completed_at"] = _now_iso()
    packet["candidate_radar_worker_execution_request_receipt"] = receipt
    packet["candidate_radar_worker_execution_request_rows"] = receipt_rows
    packet_counts = _as_dict(packet.get("counts"))
    packet_counts["candidate_radar_worker_execution_request_row_count"] = len(receipt_rows)
    packet_counts["candidate_radar_worker_execution_request_local_blocker_count"] = receipt.get(
        "local_blocker_count", 0
    )
    packet_counts["candidate_radar_worker_execution_request_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    packet_counts["candidate_radar_worker_execution_request_ready"] = receipt.get("local_execution_request_ready") is True
    packet["counts"] = packet_counts
    packet_policy = _as_dict(packet.get("policy"))
    packet_policy["candidate_radar_worker_execution_request_is_button_gated"] = True
    packet_policy["candidate_radar_worker_execution_request_is_local"] = True
    packet_policy["candidate_radar_worker_execution_request_does_not_start_worker"] = True
    packet_policy["candidate_radar_worker_execution_request_is_not_production_replacement"] = True
    packet_policy["candidate_radar_worker_execution_request_keeps_external_calls_false"] = True
    packet["policy"] = packet_policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 worker execution request 已写入本地申请票据；真实 worker full-pool/deep-scan、provider parity、DeepSeek 和 production replacement 仍未执行。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "worker execution request" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "worker_execution_request_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_worker_execution_request_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_worker_execution_request_storage_write_failed",
            error_message_safe="candidate_radar_worker_execution_request_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_worker_execution_request_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_worker_execution_request_ready",
        call_ledger=[ledger],
        warning="candidate_radar_worker_execution_request_ready_no_external_call",
    ) or task


def run_candidate_full_pool_worker_fallback_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_FULL_POOL_WORKER_FALLBACK_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_full_pool_worker_fallback_queued",
        warnings=[
            "下一票雷达 full-pool worker fallback 只运行本地 fallback 路线；不会启动 Redis/Celery worker。",
            "fallback 不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_candidate_radar_worker_fallback_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    current_packet = read_candidate_radar_cache()
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    if not _as_list(snapshot_map.get("next_ticket_candidates")) and _as_list(current_packet.get("next_ticket_candidates")):
        snapshot_map["next_ticket_candidates"] = _as_list(current_packet.get("next_ticket_candidates"))
    if not _as_dict(snapshot_map.get("radar_packet")) and _as_dict(current_packet.get("radar_packet")):
        snapshot_map["radar_packet"] = _as_dict(current_packet.get("radar_packet"))
    scan_snapshot, local_pool_audit, local_pool_skipped_rows = _snapshot_with_local_candidate_pool(
        snapshot_map,
        payload_safe,
        "full_pool_local_scan",
    )
    now = _now_iso()
    plan = _build_full_pool_scan_plan(scan_snapshot, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "full_pool_worker_fallback",
        "local_worker_fallback_only": True,
        "operator_approved": _coerce_bool(
            payload_safe.get("operator_approved")
            or payload_safe.get("user_approved")
            or payload_safe.get("approved"),
            False,
        ),
        "worker_execution_scope_hash_short": _safe_text(
            payload_safe.get("worker_execution_scope_hash") or payload_safe.get("scope_hash") or "",
            limit=128,
        )[:16],
        "input_candidate_count": local_pool_audit.get("input_candidate_count"),
        "normalized_candidate_count": local_pool_audit.get("normalized_candidate_count"),
        "external_sources_allowed": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "provider_backed_acceptance_done": False,
        "production_full_pool_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        scan_snapshot,
        mode="full_pool_worker_fallback",
        cache_source="full_pool_worker_fallback_task",
        scan_mode="full_pool_local_scan",
        request_params_safe=request_params_safe,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        full_pool_scan_plan=plan,
        previous_packet=previous_packet,
    )
    for key in [
        "candidate_radar_worker_execution_recipe",
        "candidate_radar_worker_execution_rows",
        "candidate_radar_worker_execution_request_receipt",
        "candidate_radar_worker_execution_request_rows",
        "provider_parity_dry_run_receipt",
        "provider_parity_dry_run_rows",
        "search_quant_projection_acceptance_dry_run_receipt",
        "search_quant_projection_acceptance_dry_run_rows",
        "search_quant_projection_execution_request_receipt",
        "search_quant_projection_execution_request_rows",
        "candidate_browser_qa_review_contract",
        "candidate_browser_qa_review_rows",
    ]:
        if key in current_packet:
            packet[key] = current_packet[key]
    receipt, receipt_rows = _candidate_radar_full_pool_worker_fallback_receipt(
        packet,
        payload_safe=payload_safe,
        explicit_execution=True,
        task_id=str(task["task_id"]),
        executed_at=now,
    )
    request_params_safe["requested_worker_execution_scope_hash_matches_latest"] = receipt.get(
        "requested_worker_execution_scope_hash_matches_latest"
    )
    request_params_safe["local_worker_fallback_full_pool_done"] = receipt.get("local_worker_fallback_full_pool_done")
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_full_pool_worker_fallback",
        source_snapshot=str(local_pool_audit.get("input_source") or "local_universe_payload_or_cache"),
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=receipt.get("status") or "candidate_radar_full_pool_worker_fallback_recorded",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "full_pool_worker_fallback"
    packet["full_pool_worker_fallback_completed_at"] = now
    packet["candidate_radar_full_pool_worker_fallback_receipt"] = receipt
    packet["candidate_radar_full_pool_worker_fallback_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_full_pool_worker_fallback_row_count"] = len(receipt_rows)
    counts["candidate_radar_full_pool_worker_fallback_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_full_pool_worker_fallback_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_full_pool_worker_fallback_ready"] = (
        receipt.get("local_worker_fallback_full_pool_done") is True
    )
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_full_pool_worker_fallback_is_button_gated"] = True
    policy["candidate_radar_full_pool_worker_fallback_is_local"] = True
    policy["candidate_radar_full_pool_worker_fallback_does_not_start_worker"] = True
    policy["candidate_radar_full_pool_worker_fallback_is_not_production_replacement"] = True
    policy["candidate_radar_full_pool_worker_fallback_keeps_external_calls_false"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 full-pool worker fallback 已运行本地 fallback 并写入收据；真实 Celery/Redis worker、provider parity、browser promotion 和 production replacement 仍未完成。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "full-pool worker fallback" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "full_pool_worker_fallback_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_full_pool_worker_fallback_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_full_pool_worker_fallback_storage_write_failed",
            error_message_safe="candidate_radar_full_pool_worker_fallback_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_full_pool_worker_fallback_failed_no_external_call",
        ) or task

    final_step = (
        "candidate_radar_full_pool_worker_fallback_ready"
        if receipt.get("local_worker_fallback_full_pool_done") is True
        else "candidate_radar_full_pool_worker_fallback_blocked_local_review"
    )
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning="candidate_radar_full_pool_worker_fallback_recorded_no_external_call",
    ) or task


def run_candidate_deep_scan_worker_fallback_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_DEEP_SCAN_WORKER_FALLBACK_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_deep_scan_worker_fallback_queued",
        warnings=[
            "下一票雷达 deep-scan worker fallback 只消费本地 deep-scan review 证据；不会启动 Redis/Celery worker。",
            "fallback 不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_candidate_radar_deep_scan_worker_fallback_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    now = _now_iso()
    receipt, receipt_rows = _candidate_radar_deep_scan_worker_fallback_receipt(
        packet,
        payload_safe=payload_safe,
        explicit_execution=True,
        task_id=str(task["task_id"]),
        executed_at=now,
    )
    request_params_safe = {
        "scan_mode": "deep_scan_worker_fallback",
        "local_worker_fallback_only": True,
        "operator_approved": receipt.get("operator_approved") is True,
        "worker_execution_scope_hash_short": receipt.get("worker_execution_scope_hash_short") or "",
        "requested_worker_execution_scope_hash_matches_latest": receipt.get(
            "requested_worker_execution_scope_hash_matches_latest"
        )
        is True,
        "local_deep_scan_review_done": receipt.get("local_deep_scan_review_done") is True,
        "local_worker_fallback_deep_scan_done": receipt.get("local_worker_fallback_deep_scan_done") is True,
        "candidate_row_count": receipt.get("candidate_row_count") or 0,
        "external_sources_allowed": False,
        "worker_started": False,
        "redis_broker_used": False,
        "celery_worker_started": False,
        "provider_backed_acceptance_done": False,
        "model_execution_implemented": False,
        "deepseek_model_execution_done": False,
        "production_deep_scan_done": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_deep_scan_worker_fallback",
        source_snapshot="candidate_radar_local_deep_scan_review",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=receipt.get("status") or "candidate_radar_deep_scan_worker_fallback_recorded",
        request_params_safe=request_params_safe,
    )
    packet = dict(packet)
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "deep_scan_worker_fallback"
    packet["deep_scan_worker_fallback_completed_at"] = now
    packet["candidate_radar_deep_scan_worker_fallback_receipt"] = receipt
    packet["candidate_radar_deep_scan_worker_fallback_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_deep_scan_worker_fallback_row_count"] = len(receipt_rows)
    counts["candidate_radar_deep_scan_worker_fallback_local_blocker_count"] = receipt.get("local_blocker_count", 0)
    counts["candidate_radar_deep_scan_worker_fallback_production_blocker_count"] = receipt.get(
        "production_blocker_count", 0
    )
    counts["candidate_radar_deep_scan_worker_fallback_ready"] = (
        receipt.get("local_worker_fallback_deep_scan_done") is True
    )
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_deep_scan_worker_fallback_is_button_gated"] = True
    policy["candidate_radar_deep_scan_worker_fallback_is_local"] = True
    policy["candidate_radar_deep_scan_worker_fallback_does_not_start_worker"] = True
    policy["candidate_radar_deep_scan_worker_fallback_does_not_call_deepseek"] = True
    policy["candidate_radar_deep_scan_worker_fallback_is_not_production_replacement"] = True
    policy["candidate_radar_deep_scan_worker_fallback_keeps_external_calls_false"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 deep-scan worker fallback 已写入本地收据；真实 Celery/Redis worker、DeepSeek/model ledger、provider parity、browser promotion 和 production replacement 仍未完成。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "deep-scan worker fallback" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "deep_scan_worker_fallback_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_deep_scan_worker_fallback_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_deep_scan_worker_fallback_storage_write_failed",
            error_message_safe="candidate_radar_deep_scan_worker_fallback_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_deep_scan_worker_fallback_failed_no_external_call",
        ) or task

    final_step = (
        "candidate_radar_deep_scan_worker_fallback_ready"
        if receipt.get("local_worker_fallback_deep_scan_done") is True
        else "candidate_radar_deep_scan_worker_fallback_blocked_local_review"
    )
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning="candidate_radar_deep_scan_worker_fallback_recorded_no_external_call",
    ) or task


def run_candidate_full_pool_plan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_full_pool_plan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_full_pool_plan_queued",
        warnings=[
            "下一票雷达 full-pool plan 只生成本地准备度计划；不会扫描全市场、不会调用 Tushare、DeepSeek 或 GitHub。",
            "计划结果只说明 worker、freshness、provider 覆盖和 legacy parity 阻断项；不会生成买入候选或修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_plan_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    now = _now_iso()
    plan = _build_full_pool_scan_plan(snapshot_map, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "full_pool_scan",
        "plan_only": True,
        "filter_count": len(plan.get("filter_rows") or []),
        "required_signal_group_count": plan.get("required_signal_group_count"),
        "blocking_issue_count": plan.get("blocking_issue_count"),
        "external_sources_allowed": False,
        "full_pool_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="full_pool_plan",
        cache_source="full_pool_plan_task",
        scan_mode="full_pool_plan",
        request_params_safe=request_params_safe,
        full_pool_scan_plan=plan,
        previous_packet=previous_packet,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_full_pool_plan",
        source_snapshot="command_center_latest.json",
        row_count=len(plan.get("blocker_rows") or []),
        call_status="full_pool_plan_ready",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["full_pool_plan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 full-pool plan 只记录准备度和阻断项；不扫描全市场、不刷新 provider、不生成买入候选。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "full-pool plan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "full_pool_plan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_full_pool_plan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_full_pool_plan_storage_write_failed",
            error_message_safe="candidate_radar_full_pool_plan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_full_pool_plan_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_full_pool_plan_ready",
        call_ledger=[ledger],
        warning="candidate_radar_full_pool_plan_ready_no_external_call",
    ) or task


def run_candidate_full_pool_local_scan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_full_pool_local_scan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_full_pool_local_scan_queued",
        warnings=[
            "下一票雷达 full-pool local scan 只消费本地 universe/payload/cache；不会调用 Tushare、DeepSeek 或 GitHub。",
            "本地 full-pool 执行收据不是 provider-backed 全市场生产验收，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_full_pool_universe",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    scan_snapshot, local_pool_audit, local_pool_skipped_rows = _snapshot_with_local_candidate_pool(
        snapshot_map,
        payload_safe,
        "full_pool_local_scan",
    )
    now = _now_iso()
    plan = _build_full_pool_scan_plan(scan_snapshot, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "full_pool_local_scan",
        "local_execution_only": True,
        "input_candidate_count": local_pool_audit.get("input_candidate_count"),
        "normalized_candidate_count": local_pool_audit.get("normalized_candidate_count"),
        "truncated_candidate_count": local_pool_audit.get("truncated_candidate_count"),
        "external_sources_allowed": False,
        "provider_backed_acceptance_done": False,
        "production_full_pool_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        scan_snapshot,
        mode="full_pool_local_scan",
        cache_source="full_pool_local_scan_task",
        scan_mode="full_pool_local_scan",
        request_params_safe=request_params_safe,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        full_pool_scan_plan=plan,
        previous_packet=previous_packet,
    )
    receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_full_pool_local_scan",
        source_snapshot=str(local_pool_audit.get("input_source") or "local_universe_payload_or_cache"),
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=receipt.get("status") or "full_pool_local_execution_ready_production_pending",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["full_pool_local_scan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 full-pool local scan 已消费本地 universe 并写入执行收据；不刷新 provider、不调用模型、不代表 provider-backed 全市场验收。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "full-pool local scan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "full_pool_local_scan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_full_pool_local_scan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_full_pool_local_scan_storage_write_failed",
            error_message_safe="candidate_radar_full_pool_local_scan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_full_pool_local_scan_failed_no_external_call",
        ) or task

    final_step = "candidate_radar_full_pool_local_scan_completed"
    final_warning = "candidate_radar_full_pool_local_scan_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_step = "candidate_radar_full_pool_local_scan_empty_universe"
        final_warning = "candidate_radar_full_pool_local_scan_empty_universe_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning=final_warning,
    ) or task


def run_candidate_deep_scan_plan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_deep_scan_plan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_deep_scan_plan_queued",
        warnings=[
            "下一票雷达 deep-scan plan 只生成本地功能覆盖和准备度清单；不会扫描全市场、不会调用 Tushare、DeepSeek 或 GitHub。",
            "deep-scan plan 用来防止迁移降能；它不是 deep_scan 完成，不生成买入候选，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_deep_scan_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    now = _now_iso()
    plan = _build_deep_scan_plan(snapshot_map, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "deep_scan",
        "plan_only": True,
        "scan_depth": plan.get("requested_depth"),
        "required_signal_group_count": plan.get("required_signal_group_count"),
        "legacy_feature_gap_count": plan.get("legacy_feature_gap_count"),
        "blocking_issue_count": plan.get("blocking_issue_count"),
        "external_sources_allowed": False,
        "deep_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="deep_scan_plan",
        cache_source="deep_scan_plan_task",
        scan_mode="deep_scan_plan",
        request_params_safe=request_params_safe,
        deep_scan_plan=plan,
        previous_packet=previous_packet,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_deep_scan_plan",
        source_snapshot="command_center_latest.json",
        row_count=len(plan.get("blocker_rows") or []),
        call_status="deep_scan_plan_ready",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["deep_scan_plan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 deep-scan plan 只记录功能覆盖、provider、freshness、worker 和交易隔离准备度；不执行 deep_scan、不刷新 provider、不调用 DeepSeek、不生成买入候选。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "deep-scan plan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "deep_scan_plan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_deep_scan_plan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_deep_scan_plan_storage_write_failed",
            error_message_safe="candidate_radar_deep_scan_plan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_deep_scan_plan_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_deep_scan_plan_ready",
        call_ledger=[ledger],
        warning="candidate_radar_deep_scan_plan_ready_no_external_call",
    ) or task


def run_candidate_deep_scan_local_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_deep_scan_local_review",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_deep_scan_local_review_queued",
        warnings=[
            "下一票雷达 deep-scan local review 只审查本地候选证据、parity、provider 和 freshness 缺口；不会调用 Tushare、DeepSeek 或 GitHub。",
            "本地 deep review 不是 deep_scan 完成，不生成买入候选，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_deep_scan_review_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    now = _now_iso()
    plan = _build_deep_scan_plan(snapshot_map, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "deep_scan_local_review",
        "local_review_only": True,
        "scan_depth": plan.get("requested_depth"),
        "legacy_feature_gap_count": plan.get("legacy_feature_gap_count"),
        "provider_gap_count": plan.get("provider_gap_count"),
        "external_sources_allowed": False,
        "deep_scan_done": False,
        "deepseek_called": False,
        "provider_refresh_executed": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="deep_scan_local_review",
        cache_source="deep_scan_local_review_task",
        scan_mode="deep_scan_local_review",
        request_params_safe=request_params_safe,
        deep_scan_plan=plan,
        previous_packet=previous_packet,
    )
    receipt = _as_dict(packet.get("deep_scan_local_review_receipt"))
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_deep_scan_local_review",
        source_snapshot="command_center_latest.json",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=receipt.get("status") or "deep_scan_local_review_ready_production_pending",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["deep_scan_local_review_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 deep-scan local review 已写入本地审查收据；不刷新 provider、不调用 DeepSeek、不代表 deep_scan 生产验收完成。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "deep-scan local review" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "deep_scan_local_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_deep_scan_local_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_deep_scan_local_review_storage_write_failed",
            error_message_safe="candidate_radar_deep_scan_local_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_deep_scan_local_review_failed_no_external_call",
        ) or task

    final_step = "candidate_radar_deep_scan_local_review_completed"
    final_warning = "candidate_radar_deep_scan_local_review_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_step = "candidate_radar_deep_scan_local_review_empty_candidates"
        final_warning = "candidate_radar_deep_scan_local_review_empty_candidates_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning=final_warning,
    ) or task


def run_candidate_browser_qa_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_browser_qa_review",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_browser_qa_review_queued",
        warnings=[
            "候选雷达 browser QA review 只读取本地 ignored runner 报告；不会打开浏览器、不会启动服务、不会调用 Tushare/DeepSeek/GitHub。",
            "review 结果只代表本地 artifact 审查状态；不代表 full-pool/deep-scan/provider-backed 验收或 production radar replacement。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_candidate_browser_qa_evidence",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    evidence_summary = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    evidence_rows = [row for row in _as_list(packet.get("candidate_browser_qa_evidence_rows")) if isinstance(row, dict)]
    reviewed_at = _now_iso()
    review_contract = _candidate_browser_qa_review_contract(
        evidence_summary,
        evidence_rows,
        explicit_review=True,
        task_id=task["task_id"],
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "candidate_route_browser_qa_local_artifact",
        "candidate_route": "#candidates",
        "external_sources_allowed": False,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "production_radar_replacement_complete": False,
    }
    request_params_safe.update(
        {
            key: payload_safe.get(key)
            for key in ("review_note", "reviewer")
            if payload_safe.get(key) is not None
        }
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_browser_qa_review",
        source_snapshot=".stock_ming_3/motion_qa",
        row_count=len(review_contract.get("rows") or []),
        call_status=review_contract["status"],
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["candidate_browser_qa_review_completed_at"] = reviewed_at
    packet["candidate_browser_qa_review_contract"] = review_contract
    packet["candidate_browser_qa_review_rows"] = review_contract["rows"]
    counts = _as_dict(packet.get("counts"))
    counts["candidate_browser_qa_review_blocking_count"] = review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = review_contract["local_browser_qa_review_ready"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_browser_qa_review_is_button_gated"] = True
    policy["candidate_browser_qa_review_does_not_open_browser"] = True
    policy["candidate_browser_qa_review_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "候选雷达 browser QA review 只审查本地 ignored artifact；不打开浏览器、不提交截图、不调用 provider、不完成生产雷达替代。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "browser QA review" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "browser_qa_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_browser_qa_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_browser_qa_review_storage_write_failed",
            error_message_safe="candidate_radar_browser_qa_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_browser_qa_review_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_browser_qa_review_ready",
        call_ledger=[ledger],
        warning="candidate_radar_browser_qa_review_ready_no_external_call",
    ) or task


def run_candidate_production_replacement_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PRODUCTION_REPLACEMENT_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_production_replacement_review_queued",
        warnings=[
            "下一票雷达 production replacement review 只审查本地迁移证据；不会启动 worker、不会调用 Tushare、DeepSeek 或 GitHub。",
            "review 收据不代表生产雷达替代完成，不退掉 legacy fallback，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_production_replacement_review",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    reviewed_at = _now_iso()
    receipt, receipt_rows = _candidate_radar_production_replacement_review(
        packet,
        payload_safe=payload_safe,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "candidate_radar_production_replacement_local_review",
        "operator_approved": _coerce_bool(
            payload_safe.get("operator_approved") or payload_safe.get("approved_by_user") or payload_safe.get("approved"),
            False,
        ),
        "reviewer": receipt.get("reviewer"),
        "review_scope_hash_short": receipt.get("review_scope_hash_short"),
        "local_review_ready": receipt.get("local_review_ready"),
        "production_blocker_count": receipt.get("production_blocker_count"),
        "external_sources_allowed": False,
        "worker_started": False,
        "worker_task_created": False,
        "worker_task_executed": False,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_production_replacement_review",
        source_snapshot="candidate_radar_cache",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_radar_production_replacement_review_recorded"),
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "production_replacement_review"
    packet["candidate_radar_production_replacement_review_completed_at"] = reviewed_at
    packet["candidate_radar_production_replacement_review_receipt"] = receipt
    packet["candidate_radar_production_replacement_review_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_production_replacement_review_row_count"] = receipt["row_count"]
    counts["candidate_radar_production_replacement_review_local_blocker_count"] = receipt["local_blocker_count"]
    counts["candidate_radar_production_replacement_review_production_blocker_count"] = receipt[
        "production_blocker_count"
    ]
    counts["candidate_radar_production_replacement_review_ready"] = receipt["local_review_ready"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_production_replacement_review_is_button_gated"] = True
    policy["candidate_radar_production_replacement_review_is_local"] = True
    policy["candidate_radar_production_replacement_review_does_not_call_provider_or_model"] = True
    policy["candidate_radar_production_replacement_review_does_not_start_worker"] = True
    policy["candidate_radar_production_replacement_review_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 production replacement review 已写入本地审查收据；真实 worker/provider/model/browser promotion 和 legacy retirement 仍未执行。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "production replacement review" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "production_replacement_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_production_replacement_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_production_replacement_review_storage_write_failed",
            error_message_safe="candidate_radar_production_replacement_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_production_replacement_review_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_production_replacement_review_ready",
        call_ledger=[ledger],
        warning="candidate_radar_production_replacement_review_ready_no_external_call",
    ) or task


def run_candidate_production_promotion_dry_run_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PRODUCTION_PROMOTION_DRY_RUN_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_production_promotion_dry_run_queued",
        warnings=[
            "下一票雷达 production promotion dry-run 只绑定本地 production review scope；不会启动 worker、不会调用 Tushare、DeepSeek 或 GitHub。",
            "dry-run 不代表生产雷达替代完成，不退掉 legacy fallback，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_production_promotion_dry_run",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    created_at = _now_iso()
    receipt, receipt_rows = _candidate_radar_production_promotion_dry_run_receipt(
        packet,
        payload_safe=payload_safe,
        explicit_dry_run=True,
        task_id=str(task["task_id"]),
        created_at=created_at,
    )
    request_params_safe = {
        "promotion_scope": "candidate_radar_production_promotion_local_dry_run",
        "operator_approved": receipt.get("operator_approved") is True,
        "production_replacement_review_scope_hash_short": receipt.get(
            "production_replacement_review_scope_hash_short"
        )
        or "",
        "requested_review_scope_hash_matches_latest": receipt.get(
            "requested_review_scope_hash_matches_latest"
        )
        is True,
        "promotion_scope_hash_short": receipt.get("promotion_scope_hash_short") or "",
        "ready_for_local_promotion_review": receipt.get("ready_for_local_promotion_review") is True,
        "production_blocker_count": receipt.get("production_blocker_count") or 0,
        "external_sources_allowed": False,
        "worker_started": False,
        "worker_task_created": False,
        "provider_model_task_created": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_production_promotion_dry_run",
        source_snapshot="candidate_radar_production_replacement_review",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_radar_production_promotion_dry_run_recorded"),
        request_params_safe=request_params_safe,
    )
    packet = dict(packet)
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "production_promotion_dry_run"
    packet["candidate_radar_production_promotion_dry_run_completed_at"] = created_at
    packet["candidate_radar_production_promotion_dry_run_receipt"] = receipt
    packet["candidate_radar_production_promotion_dry_run_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_production_promotion_dry_run_row_count"] = receipt["row_count"]
    counts["candidate_radar_production_promotion_dry_run_local_blocker_count"] = receipt["local_blocker_count"]
    counts["candidate_radar_production_promotion_dry_run_production_blocker_count"] = receipt[
        "production_blocker_count"
    ]
    counts["candidate_radar_production_promotion_dry_run_ready"] = receipt["ready_for_local_promotion_review"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_production_promotion_dry_run_is_button_gated"] = True
    policy["candidate_radar_production_promotion_dry_run_is_local"] = True
    policy["candidate_radar_production_promotion_dry_run_does_not_start_worker"] = True
    policy["candidate_radar_production_promotion_dry_run_calls_no_provider_model_github"] = True
    policy["candidate_radar_production_promotion_dry_run_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 production promotion dry-run 已写入本地 scope 票据；真实 worker/provider/model/browser promotion 和 legacy retirement 仍未执行。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "production promotion dry-run" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "production_promotion_dry_run_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_production_promotion_dry_run_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_production_promotion_dry_run_storage_write_failed",
            error_message_safe="candidate_radar_production_promotion_dry_run_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_production_promotion_dry_run_failed_no_external_call",
        ) or task

    final_step = (
        "candidate_radar_production_promotion_dry_run_ready"
        if receipt.get("ready_for_local_promotion_review") is True
        else "candidate_radar_production_promotion_dry_run_blocked_local_review"
    )
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning="candidate_radar_production_promotion_dry_run_ready_no_external_call",
    ) or task


def run_candidate_legacy_retirement_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_LEGACY_RETIREMENT_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_legacy_retirement_review_queued",
        warnings=[
            "下一票雷达 legacy retirement review 只审查本地退场边界；不会启动 worker、不会调用 Tushare、DeepSeek 或 GitHub。",
            "review 收据不代表 legacy 已可退场，不删除 Streamlit fallback，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_legacy_retirement_review",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    reviewed_at = _now_iso()
    receipt, receipt_rows = _candidate_radar_legacy_retirement_review_receipt(
        packet,
        payload_safe=payload_safe,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "candidate_radar_legacy_retirement_local_review",
        "operator_approved": receipt.get("operator_approved") is True,
        "reviewer": receipt.get("reviewer") or "",
        "retirement_scope_hash_short": receipt.get("retirement_scope_hash_short") or "",
        "local_review_ready": receipt.get("local_review_ready") is True,
        "production_blocker_count": receipt.get("production_blocker_count") or 0,
        "external_sources_allowed": False,
        "worker_started": False,
        "worker_task_created": False,
        "provider_model_task_created": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_legacy_retirement_review",
        source_snapshot="candidate_radar_production_promotion_dry_run",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_radar_legacy_retirement_review_recorded"),
        request_params_safe=request_params_safe,
    )
    packet = dict(packet)
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "legacy_retirement_review"
    packet["candidate_radar_legacy_retirement_review_completed_at"] = reviewed_at
    packet["candidate_radar_legacy_retirement_review_receipt"] = receipt
    packet["candidate_radar_legacy_retirement_review_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_legacy_retirement_review_row_count"] = receipt["row_count"]
    counts["candidate_radar_legacy_retirement_review_local_blocker_count"] = receipt["local_blocker_count"]
    counts["candidate_radar_legacy_retirement_review_production_blocker_count"] = receipt[
        "production_blocker_count"
    ]
    counts["candidate_radar_legacy_retirement_review_ready"] = receipt["local_review_ready"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_legacy_retirement_review_is_button_gated"] = True
    policy["candidate_radar_legacy_retirement_review_is_local"] = True
    policy["candidate_radar_legacy_retirement_review_does_not_start_worker"] = True
    policy["candidate_radar_legacy_retirement_review_calls_no_provider_model_github"] = True
    policy["candidate_radar_legacy_retirement_review_is_not_legacy_retirement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 legacy retirement review 已写入本地审查收据；真实 worker/provider/model/browser promotion 和 release evidence 未完成前 legacy fallback 仍保留。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "legacy retirement review" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "legacy_retirement_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_legacy_retirement_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_legacy_retirement_review_storage_write_failed",
            error_message_safe="candidate_radar_legacy_retirement_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_legacy_retirement_review_failed_no_external_call",
        ) or task

    final_step = (
        "candidate_radar_legacy_retirement_review_ready"
        if receipt.get("local_review_ready") is True
        else "candidate_radar_legacy_retirement_review_blocked_local_review"
    )
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning="candidate_radar_legacy_retirement_review_ready_no_external_call",
    ) or task


def run_candidate_production_promotion_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        CANDIDATE_PRODUCTION_PROMOTION_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_production_promotion_review_queued",
        warnings=[
            "下一票雷达 production promotion review 只审查本地 promotion 边界；不会启动 worker、不会调用 Tushare、DeepSeek 或 GitHub。",
            "review 收据不代表生产雷达替代完成，不退掉 legacy fallback，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="building_candidate_radar_production_promotion_review",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    reviewed_at = _now_iso()
    receipt, receipt_rows = _candidate_radar_production_promotion_review_receipt(
        packet,
        payload_safe=payload_safe,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "candidate_radar_production_promotion_local_review",
        "operator_approved": receipt.get("operator_approved") is True,
        "reviewer": receipt.get("reviewer") or "",
        "promotion_scope_hash_short": receipt.get("promotion_scope_hash_short") or "",
        "requested_promotion_scope_hash_matches_latest": receipt.get(
            "requested_promotion_scope_hash_matches_latest"
        )
        is True,
        "promotion_review_scope_hash_short": receipt.get("promotion_review_scope_hash_short") or "",
        "local_review_ready": receipt.get("local_review_ready") is True,
        "production_blocker_count": receipt.get("production_blocker_count") or 0,
        "external_sources_allowed": False,
        "worker_started": False,
        "worker_task_created": False,
        "provider_model_task_created": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
    }
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_production_promotion_review",
        source_snapshot="candidate_radar_legacy_retirement_review",
        row_count=len(receipt_rows),
        call_status=str(receipt.get("status") or "candidate_radar_production_promotion_review_recorded"),
        request_params_safe=request_params_safe,
    )
    packet = dict(packet)
    packet["task_id"] = task["task_id"]
    packet["scan_mode"] = "production_promotion_review"
    packet["candidate_radar_production_promotion_review_completed_at"] = reviewed_at
    packet["candidate_radar_production_promotion_review_receipt"] = receipt
    packet["candidate_radar_production_promotion_review_rows"] = receipt_rows
    counts = _as_dict(packet.get("counts"))
    counts["candidate_radar_production_promotion_review_row_count"] = receipt["row_count"]
    counts["candidate_radar_production_promotion_review_local_blocker_count"] = receipt["local_blocker_count"]
    counts["candidate_radar_production_promotion_review_production_blocker_count"] = receipt[
        "production_blocker_count"
    ]
    counts["candidate_radar_production_promotion_review_ready"] = receipt["local_review_ready"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_radar_production_promotion_review_is_button_gated"] = True
    policy["candidate_radar_production_promotion_review_is_local"] = True
    policy["candidate_radar_production_promotion_review_does_not_start_worker"] = True
    policy["candidate_radar_production_promotion_review_calls_no_provider_model_github"] = True
    policy["candidate_radar_production_promotion_review_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 production promotion review 已写入本地审查收据；真实 worker/provider/model/browser promotion 和 release evidence 未完成前仍不能生产替代。"
    ] + [
        warning
        for warning in _as_list(packet.get("warnings"))
        if "production promotion review" not in str(warning)
    ]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "production_promotion_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_production_promotion_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_production_promotion_review_storage_write_failed",
            error_message_safe="candidate_radar_production_promotion_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_production_promotion_review_failed_no_external_call",
        ) or task

    final_step = (
        "candidate_radar_production_promotion_review_ready"
        if receipt.get("local_review_ready") is True
        else "candidate_radar_production_promotion_review_blocked_local_review"
    )
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning="candidate_radar_production_promotion_review_ready_no_external_call",
    ) or task
