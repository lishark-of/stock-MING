from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MIGRATION_PROGRESS_BASELINE = [
    {"module": "Streamlit 保留为 legacy", "current_degree": "70%"},
    {"module": "FastAPI 后端骨架", "current_degree": "60%"},
    {"module": "FastAPI 真实 cache API", "current_degree": "40%-50%"},
    {"module": "React/Vite 前端骨架", "current_degree": "60%"},
    {"module": "React 页面可用化", "current_degree": "30%-40%"},
    {"module": "Tauri 桌面壳", "current_degree": "20%"},
    {"module": "Worker / Task 系统", "current_degree": "35%-45%"},
    {"module": "Storage 层", "current_degree": "40%"},
    {"module": "Factor Quant Hub 3.0 化", "current_degree": "50%"},
    {"module": "ECharts 次日图谱", "current_degree": "30%-40%"},
    {"module": "完全替代 Streamlit 主流程", "current_degree": "20%-30%"},
]

LONG_TERM_GOAL_PROGRESS = [
    {
        "id": "LTG-01",
        "goal": "A 股交易日历级 freshness 生产化",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "45%-55%",
        "current_state": "freshness gate MVP, local matrix, synthetic long-window replay, local trade_cal artifact audit, and provider-acceptance runbook exist.",
        "not_complete_because": "provider-backed long-window trade_cal acceptance and promotion evidence are still pending.",
        "next_step": "Run an explicit provider-backed trade_cal acceptance task when approved, then promote only with safe call-ledger and freshness replay evidence.",
        "production_complete": False,
    },
    {
        "id": "LTG-02",
        "goal": "Tushare 全接口生产流水线",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "35%-45%",
        "current_state": "daily / daily_basic / moneyflow light path has real evidence; extended interfaces have matrix, local QA, runbook, dry-run contracts, and a production stage-scope manifest.",
        "not_complete_because": "full-interface provider-backed samples and promotion evidence are incomplete.",
        "next_step": "Validate target sample groups through explicit POST task runs, starting with trade_cal and then staged market-evidence domains.",
        "production_complete": False,
    },
    {
        "id": "LTG-03",
        "goal": "Factor Test Lab 完整生产化",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "45%-55%",
        "current_state": "IC, Rank IC, ICIR, groups, drawdown, neutralization, split, decay, cost-model scaffolds, local provider blocker receipts, provider small-pool dry-run scope ticket, and production stage-scope manifest exist as research-only/preflight evidence.",
        "not_complete_because": "real provider-backed small-pool validation, larger sample coverage, and production research acceptance are still pending.",
        "next_step": "Run a separate user-approved provider-backed small-stock-pool validation bound to the safe scope ticket, then keep every metric outside strategy action.",
        "production_complete": False,
    },
    {
        "id": "LTG-04",
        "goal": "Factor 全市场 / 股票池研究",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "30%-40%",
        "current_state": "watchlist/custom/full-pool contracts, local read-plan receipts, readiness/activation receipts, local rank/zscore sufficiency audit, and worker-batch dry-run scope ticket exist.",
        "not_complete_because": "worker-backed batch execution, cross-sectional rank/zscore, neutralization, factor combination research, and full-pool validation are pending.",
        "next_step": "Implement a separate explicit worker-backed batch research task bound to the safe scope ticket after storage/worker readiness is stronger.",
        "production_complete": False,
    },
    {
        "id": "LTG-05",
        "goal": "Storage / DuckDB / Parquet 生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "50%-60%",
        "current_state": "schema/version preflight, manifest writer/validator, DuckDB read API, filters, cursor pagination, and dry-runs exist.",
        "not_complete_because": "physical schema migration, partition migration, compaction, TTL refresh execution, and cleanup execution remain pending.",
        "next_step": "Promote physical migration tasks one at a time with explicit review and no data artifacts in git.",
        "production_complete": False,
    },
    {
        "id": "LTG-06",
        "goal": "Worker / Celery / Redis 生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "35%-45%",
        "current_state": "local fallback, task lifecycle, explicit synthetic healthcheck, button-gated activation review task receipts, production evidence plan scope tickets, readiness/activation receipts, scheduler default-off policy, and worker contracts exist.",
        "not_complete_because": "real Celery/Redis process orchestration, broker healthcheck, cross-process control proof, append-only worker log proof, and production scheduler activation are pending.",
        "next_step": "Run a separate manually approved runtime QA from the production evidence plan scope ticket to collect Celery process, Redis broker, cross-process controls, append-only logs, and scheduler default-off evidence without starting processes from cache reads.",
        "production_complete": False,
    },
    {
        "id": "LTG-07",
        "goal": "DeepSeek pro 稳定解释生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "35%-45%",
        "current_state": "manual governance, sanitizer, model strategy, JSON stability audit, response-format review, retry/repair dry-run, and linkage contract exist.",
        "not_complete_because": "JSON stability target, provider-backed benchmark, provider response-format enforcement, bounded retry/repair execution, and live_light model execution are pending.",
        "next_step": "Run a larger explicit DeepSeek pro benchmark and promote only if sanitizer, parse fallback, retry/repair execution, cost, and model ledger pass.",
        "production_complete": False,
    },
    {
        "id": "LTG-08",
        "goal": "ECharts 次日操作图谱成熟版",
        "completion_bucket": "productionization_required",
        "completion_estimate": "45%-55%",
        "current_state": "payload contract, cache envelope, read-only React rendering, reference/zone/position/DeepSeek status, and interaction readiness exist.",
        "not_complete_because": "browser visual QA, performance trace, legacy parity, and production replacement evidence are pending.",
        "next_step": "Run browser QA and close interaction/legacy-parity gaps before retiring the Streamlit visual path.",
        "production_complete": False,
    },
    {
        "id": "LTG-09",
        "goal": "Tauri desktop production package",
        "completion_bucket": "productionization_required",
        "completion_estimate": "30%-40%",
        "current_state": "desktop preflight, runtime contract, backend-offline UX source contract, package QA matrix, and blocker audit exist.",
        "not_complete_because": "tauri build/package, packaged runtime QA, signing/notarization, and release evidence are pending.",
        "next_step": "Run explicit Tauri dev/build and packaged runtime QA when desktop packaging is the active focus.",
        "production_complete": False,
    },
    {
        "id": "LTG-10",
        "goal": "Streamlit 完全退出普通主流程",
        "completion_bucket": "dependent_retirement_goal",
        "completion_estimate": "40%-50%",
        "current_state": "Streamlit is marked legacy/admin/debug; retirement readiness and fallback dependency receipts exist.",
        "not_complete_because": "React/Tauri parity, no-feature-cut acceptance, and fallback retirement review are not complete.",
        "next_step": "Retire ordinary Streamlit entry points only after React/Tauri covers daily workflow and fallback blockers are clear.",
        "production_complete": False,
    },
    {
        "id": "LTG-11",
        "goal": "测试 / CI / smoke / 安全扫描标准化",
        "completion_bucket": "mostly_stable_guardrail",
        "completion_estimate": "75%-85%",
        "current_state": "local push gate, contract scripts, unit tests, frontend build, smoke, diff check, secret scan, artifact scan, CI mirror checks, release gate stage-scope manifest, and LTG stage-manifest audit visibility exist.",
        "not_complete_because": "this is an ongoing release boundary; every push candidate still needs a fresh gate run and remote CI evidence.",
        "next_step": "Keep push gate green before every push and inspect remote CI failures without calling GitHub API from cache paths.",
        "production_complete": False,
    },
    {
        "id": "LTG-12",
        "goal": "真实交易链路继续保持隔离",
        "completion_bucket": "mostly_stable_guardrail",
        "completion_estimate": "80%-90%",
        "current_state": "research/cache/task/frontend paths keep no-order, no-broker, no-action-mutation, and no-real-trade boundaries visible.",
        "not_complete_because": "trade isolation is a permanent release invariant, not a one-time feature that can be closed.",
        "next_step": "Continue proving no real trading and no strategy-action mutation in every new task, provider, model, radar, and UI path.",
        "production_complete": False,
    },
    {
        "id": "LTG-13",
        "goal": "下一票雷达快扫生产化",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "35%-45%",
        "current_state": "local quick-scan readiness, fast-scan task pipeline contract, no-feature-loss QA, legacy parity receipt, full/deep plan receipts, search-to-quant projection receipt, provider parity dry-run ticket, and result-delta clarity exist.",
        "not_complete_because": "async worker execution, real provider-backed radar parity execution, full-pool/deep-scan execution, browser performance promotion, and production replacement evidence are pending.",
        "next_step": "Use the provider parity dry-run ticket to bind the next real Tushare/DeepSeek acceptance task, then add worker-backed full-pool/deep-scan evidence without losing legacy signal groups or blocking UI.",
        "production_complete": False,
    },
    {
        "id": "LTG-14",
        "goal": "Command Center 3 动效与可视化清晰度优化",
        "completion_bucket": "later_polish_goal",
        "completion_estimate": "30%-40%",
        "current_state": "motion clarity layer, route/status cues, reduced-motion support, local runner, static QA, activation receipt, and promotion dry-run ticket exist.",
        "not_complete_because": "durable browser visual QA, performance traces, CI/release evidence, and final visual promotion are pending.",
        "next_step": "Use the promotion dry-run to bind reviewed visual/performance scope, then add durable CI/release evidence before any production motion completion claim.",
        "production_complete": False,
    },
]

LONG_TERM_GOAL_BUCKETS = {
    "mostly_stable_guardrail": "Local guardrail is useful but remains an ongoing release invariant.",
    "real_validation_required": "Local contracts or scaffolds exist, but real provider/pool/browser acceptance is still required.",
    "productionization_required": "Implementation is useful but needs production runtime, packaging, worker, storage, or visual QA promotion.",
    "dependent_retirement_goal": "Can only finish after replacement paths are accepted.",
    "later_polish_goal": "Should continue after core data, worker, desktop, and radar paths are stable.",
}

LTG_STAGE_SCOPE_MANIFESTS = {
    "LTG-01": "freshness_production_stage_scope_manifest",
    "LTG-02": "tushare_production_stage_scope_manifest",
    "LTG-03": "factor_test_production_stage_scope_manifest",
    "LTG-04": "factor_universe_worker_batch_stage_scope_manifest",
    "LTG-05": "storage_physical_migration_stage_scope_manifest",
    "LTG-06": "worker_runtime_evidence_stage_scope_manifest",
    "LTG-07": "deepseek_production_stage_scope_manifest",
    "LTG-08": "next_session_production_replacement_stage_scope_manifest",
    "LTG-09": "tauri_production_package_stage_scope_manifest",
    "LTG-10": "streamlit_retirement_stage_scope_manifest",
    "LTG-11": "release_gate_stage_scope_manifest",
    "LTG-12": "trade_isolation_stage_scope_manifest",
    "LTG-13": "candidate_radar_production_stage_scope_manifest",
    "LTG-14": "motion_production_stage_scope_manifest",
}

LTG_NEXT_EVIDENCE_REQUIRED = {
    "LTG-01": ["provider trade_cal task", "safe call ledger", "freshness replay", "promotion review"],
    "LTG-02": ["provider target samples", "full-interface selection", "failure-mode evidence", "storage promotion"],
    "LTG-03": ["provider small-pool samples", "rolling metrics", "cost/neutralization validation", "promotion review"],
    "LTG-04": ["worker batch execution", "rank/zscore", "neutralization", "full-pool validation"],
    "LTG-05": ["physical schema validation", "partition migration", "compaction", "TTL cleanup evidence"],
    "LTG-06": ["Celery/Redis process evidence", "broker healthcheck", "cross-process control", "durable task logs"],
    "LTG-07": ["larger provider benchmark", "response_format enforcement", "retry/repair evidence", "cost budget"],
    "LTG-08": ["browser visual QA", "performance trace", "Streamlit parity", "replacement promotion"],
    "LTG-09": ["tauri dev/build", "packaged runtime QA", "signing/notarization review", "release evidence"],
    "LTG-10": ["React/Tauri workflow parity", "no-feature-cut acceptance", "fallback retirement review"],
    "LTG-11": ["fresh local gate run", "remote CI status", "failure email triage", "allowlist review"],
    "LTG-12": ["continued no-broker proof", "continued no-order proof", "continued no-action mutation proof"],
    "LTG-13": ["provider parity execution", "worker full-pool scan", "worker deep-scan", "browser performance proof"],
    "LTG-14": ["browser visual QA", "performance trace", "reduced-motion proof", "durable release evidence"],
}

TARGET_STACK = [
    "React / Vite / TypeScript / Tauri",
    "FastAPI",
    "Celery / Redis / local fallback / APScheduler",
    "SQLite / DuckDB / Parquet / Redis",
    "ECharts",
    "Streamlit legacy / admin / debug",
    "Existing Python quant core reused, not rewritten",
]


def _enrich_long_term_goal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        goal_id = str(item.get("id") or "")
        next_evidence = list(LTG_NEXT_EVIDENCE_REQUIRED.get(goal_id, []))
        item["stage_scope_manifest"] = LTG_STAGE_SCOPE_MANIFESTS.get(goal_id, "")
        item["has_stage_scope_manifest"] = bool(item["stage_scope_manifest"])
        item["stage_scope_manifest_status"] = (
            "present_pending_production_evidence" if item["has_stage_scope_manifest"] else "missing"
        )
        item["next_evidence_required"] = next_evidence
        item["next_evidence_required_count"] = len(next_evidence)
        item["can_close_from_local_contracts"] = False
        item["local_contracts_are_production_evidence"] = False
        item["evidence_boundary"] = "stage_scope_manifest_is_local_guard_not_production_completion"
        enriched_rows.append(item)
    return enriched_rows


def _build_long_term_goal_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket = str(row["completion_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    stage_scope_manifest_count = sum(1 for row in rows if row.get("has_stage_scope_manifest") is True)
    return {
        "goal_count": len(rows),
        "closed_count": sum(1 for row in rows if row.get("production_complete") is True),
        "production_complete_count": sum(1 for row in rows if row.get("production_complete") is True),
        "strict_closeout": "0/14",
        "stage_scope_manifest_count": stage_scope_manifest_count,
        "stage_scope_manifest_pending_count": sum(
            1 for row in rows if row.get("stage_scope_manifest_status") == "present_pending_production_evidence"
        ),
        "goals_with_next_evidence_count": sum(1 for row in rows if int(row.get("next_evidence_required_count") or 0) > 0),
        "can_close_from_local_contracts_count": sum(
            1 for row in rows if row.get("can_close_from_local_contracts") is True
        ),
        "foundation_progress_estimate": "about_70_percent",
        "production_acceptance_estimate": "about_25_to_35_percent",
        "bucket_counts": bucket_counts,
        "bucket_meanings": dict(LONG_TERM_GOAL_BUCKETS),
        "next_priority_order": [
            "P0 push gate / local status honesty",
            "P1 LTG-01 trade_cal freshness provider acceptance",
            "P2 LTG-02 Tushare staged provider samples",
            "P3 LTG-03/LTG-13 small-pool factor and radar validation",
            "P4 LTG-05/LTG-06 storage and worker productionization",
            "P5 LTG-07/LTG-08 DeepSeek and ECharts promotion",
            "P6 LTG-09 Tauri package",
            "P7 LTG-10 Streamlit retirement",
            "P8 LTG-14 motion clarity promotion",
        ],
        "no_goal_may_close_from": ["scaffold", "preflight", "mock", "matrix", "sanitizer", "dry_run", "local_receipt"],
    }


def _linkage_row(
    *,
    linkage_key: str,
    layer: str,
    status: str,
    allowed_in_mode: str,
    next_allowed_action: str,
    required_evidence: list[str],
    external_calls_triggered: bool = False,
    tushare_called: bool = False,
    deepseek_called: bool = False,
    github_called: bool = False,
    provider_execution_implemented: bool = False,
    model_execution_implemented: bool = False,
    production_promotion_complete: bool = False,
    real_trading_connected: bool = False,
) -> dict[str, Any]:
    return {
        "linkage_key": linkage_key,
        "layer": layer,
        "status": status,
        "allowed_in_mode": allowed_in_mode,
        "next_allowed_action": next_allowed_action,
        "required_evidence": required_evidence,
        "external_calls_triggered": external_calls_triggered,
        "tushare_called": tushare_called,
        "deepseek_called": deepseek_called,
        "github_called": github_called,
        "provider_execution_implemented": provider_execution_implemented,
        "model_execution_implemented": model_execution_implemented,
        "production_promotion_complete": production_promotion_complete,
        "real_trading_connected": real_trading_connected,
        "does_not_execute_trades": not real_trading_connected,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _mode_layer_row(
    *,
    layer_order: int,
    layer_key: str,
    layer: str,
    mode_scope: str,
    current_status: str,
    allowed_action: str,
    forbidden_actions: list[str],
    required_evidence: list[str],
    provider_model_execution_allowed: bool = False,
    production_promotion_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "layer_order": layer_order,
        "layer_key": layer_key,
        "layer": layer,
        "mode_scope": mode_scope,
        "current_status": current_status,
        "allowed_action": allowed_action,
        "forbidden_actions": forbidden_actions,
        "required_evidence": required_evidence,
        "provider_model_execution_allowed": provider_model_execution_allowed,
        "production_promotion_allowed": production_promotion_allowed,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "real_trading_connected": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _build_tushare_deepseek_mode_layer_rows() -> list[dict[str, Any]]:
    return [
        _mode_layer_row(
            layer_order=1,
            layer_key="cache_render_startup",
            layer="GET cache / FastAPI startup / initial React render",
            mode_scope="cache_only/manual/live_light/live_full",
            current_status="silent_confirmed",
            allowed_action="read local cache and render existing rows",
            forbidden_actions=[
                "call Tushare from GET cache",
                "call DeepSeek from GET cache",
                "call GitHub from initial render",
                "create provider/model task before cache render",
                "mutate strategy action",
            ],
            required_evidence=["cache_get_no_provider_call", "react_render_no_provider_call", "call_ledger_external_false"],
        ),
        _mode_layer_row(
            layer_order=2,
            layer_key="post_task_creation",
            layer="explicit POST task creation",
            mode_scope="manual/live_light after opt-in and rate limit",
            current_status="button_gated_allowed",
            allowed_action="create a local task receipt or staged execution plan after explicit user/mode gate",
            forbidden_actions=[
                "direct provider/model call from React render",
                "unbounded full-pool/deep-scan task on startup",
                "GitHub probe in live_light default chain",
                "trade/order submission",
            ],
            required_evidence=["task_id", "mode", "safe_payload", "rate_limit_or_session_dedupe", "call_ledger"],
        ),
        _mode_layer_row(
            layer_order=3,
            layer_key="provider_model_execution_inside_task",
            layer="provider/model execution inside the task",
            mode_scope="manual or explicitly approved live_light",
            current_status="pending_real_call_ledger",
            allowed_action="run scoped Tushare light APIs and optional DeepSeek pro explanation only inside approved task execution",
            forbidden_actions=[
                "mark dry-run as real Tushare rows",
                "treat DeepSeek as data source",
                "allow parse_failed output into packet",
                "overwrite numeric fields, prices, holdings, operation_zones, or strategy action",
            ],
            required_evidence=[
                "Tushare call_ledger api/provider/request_params_safe",
                "row_count/data_date/local_fetched_at/call_status/error_message_safe",
                "DeepSeek model_used/status/token_usage/parse_status/cache_hit_or_miss/input_hash/output_hash",
                "six_field_sanitizer",
            ],
            provider_model_execution_allowed=True,
        ),
        _mode_layer_row(
            layer_order=4,
            layer_key="production_promotion_evidence",
            layer="production promotion review",
            mode_scope="manual review only",
            current_status="blocked_until_real_provider_model_browser_redaction_evidence",
            allowed_action="promote only after real provider/model ledgers, UI non-blocking proof, redaction review, and production review are complete",
            forbidden_actions=[
                "promote from scaffold/preflight/matrix/sanitizer/dry-run/local receipt",
                "hide credential or ledger redaction gaps",
                "retire fallback before provider/browser evidence",
                "connect real trading",
            ],
            required_evidence=[
                "real_tushare_call_ledger",
                "deepseek_model_ledger_if_enabled",
                "browser_nonblocking_evidence",
                "ledger_redaction_review",
                "production_promotion_review",
            ],
            production_promotion_allowed=False,
        ),
    ]


def _build_tushare_deepseek_linkage_rows() -> list[dict[str, Any]]:
    return [
        _linkage_row(
            linkage_key="cache_startup_render_boundary",
            layer="GET cache / FastAPI startup / initial React render",
            status="offline_enforced",
            allowed_in_mode="cache_only/manual/live_light/live_full",
            next_allowed_action="keep initial render provider/model silent",
            required_evidence=["cache_get_no_provider_call", "react_render_no_provider_call"],
        ),
        _linkage_row(
            linkage_key="live_light_post_task_creation",
            layer="React mounted behavior after first cache render",
            status="allowed_only_after_opt_in_rate_limited_post_task",
            allowed_in_mode="live_light",
            next_allowed_action="POST /api/bootstrap/live-startup after cache render and rate-limit check",
            required_evidence=["visible_runtime_mode", "task_id", "rate_limit_or_session_dedupe", "safe_failure"],
        ),
        _linkage_row(
            linkage_key="tushare_light_provider_execution",
            layer="provider execution inside task",
            status="pending_real_call_ledger",
            allowed_in_mode="manual/live_light",
            next_allowed_action="run user-approved task for trade_cal/daily/daily_basic/moneyflow only",
            required_evidence=["api", "provider", "request_params_safe", "row_count", "data_date", "local_fetched_at", "call_status", "error_message_safe"],
        ),
        _linkage_row(
            linkage_key="deepseek_pro_after_task_execution",
            layer="model execution after data readiness",
            status="pending_model_ledger_and_benchmark",
            allowed_in_mode="manual/live_light_optional",
            next_allowed_action="run user-approved DeepSeek pro explanation after Tushare/factor/next-session cache is ready",
            required_evidence=["model_used", "status", "token_usage", "parse_status", "cache_hit_or_miss", "input_hash", "output_hash", "six_field_sanitizer"],
        ),
        _linkage_row(
            linkage_key="github_probe_boundary",
            layer="GitHub probe",
            status="manual_only_excluded_from_live_light_default_chain",
            allowed_in_mode="manual",
            next_allowed_action="keep GitHub probe button-gated and out of live_light startup",
            required_evidence=["explicit_user_action", "no_live_light_default_probe"],
        ),
        _linkage_row(
            linkage_key="production_promotion_boundary",
            layer="production acceptance promotion",
            status="blocked_until_provider_model_browser_and_redaction_evidence",
            allowed_in_mode="manual_review",
            next_allowed_action="promote only after real call ledger, model ledger, UI non-blocking evidence, redaction review, and production review",
            required_evidence=["real_tushare_call_ledger", "deepseek_model_ledger_if_enabled", "browser_nonblocking_evidence", "ledger_redaction_review", "production_promotion_review"],
        ),
        _linkage_row(
            linkage_key="real_trading_boundary",
            layer="broker/order/trade execution",
            status="disconnected",
            allowed_in_mode="none",
            next_allowed_action="keep real trading isolated in a separate future project",
            required_evidence=["no_broker_adapter", "no_order_endpoint", "no_strategy_action_mutation"],
        ),
    ]


def _build_tushare_deepseek_linkage_review(
    linkage_rows: list[dict[str, Any]],
    mode_layer_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    blocking_rows = [
        row
        for row in linkage_rows
        if row.get("provider_execution_implemented") is True
        or row.get("model_execution_implemented") is True
        or row.get("production_promotion_complete") is True
        or row.get("real_trading_connected") is True
    ]
    return {
        "status": "linkage_contract_visible_provider_model_execution_pending",
        "schema_version": "command_center_3_tushare_deepseek_linkage_review.v1",
        "row_count": len(linkage_rows),
        "mode_layer_row_count": len(mode_layer_rows),
        "mode_layer_model": "cache_render_startup -> post_task_creation -> provider_model_execution_inside_task -> production_promotion_evidence",
        "boundary_interpretation": "mode_layered_not_absolute_global_ban",
        "blocking_row_count": len(blocking_rows),
        "cache_get_calls_tushare": False,
        "cache_get_calls_deepseek": False,
        "react_render_calls_tushare": False,
        "react_render_calls_deepseek": False,
        "cache_render_silent": True,
        "live_light_post_task_allowed": True,
        "post_task_creation_button_gated": True,
        "provider_model_execution_pending": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_promotion_pending": True,
        "production_promotion_complete": False,
        "real_trading_disconnected": True,
        "allowed_tushare_light_scope": ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"],
        "deepseek_allowed_after_data_ready": True,
        "deepseek_sanitizer_schema": [
            "summary",
            "support_notes",
            "suppress_notes",
            "conflict_notes",
            "missing_data_notes",
            "discipline_notes",
        ],
        "blocked_boundaries": [
            "no GET/cache provider call",
            "no React direct provider/model call",
            "no GitHub probe in live_light default chain",
            "no strategy action mutation",
            "no real trading",
            "no token/key exposure",
            "no full-pool/deep-scan on render",
        ],
        "next_review": "Before real live_light promotion, require explicit provider call ledger, DeepSeek model ledger, redaction review, UI non-blocking evidence, and production promotion evidence.",
    }

MIGRATION_PRINCIPLES = [
    "不砍功能。",
    "Streamlit 不再作为普通主流程。",
    "重计算、Tushare、DeepSeek、GitHub 校验全部任务化 / 按钮门控。",
    "前端只通过 FastAPI 获取数据。",
    "cache API 永不外联。",
    "POST task 才可能触发外部请求。",
    "所有外部请求必须有 call_ledger。",
    "不执行真实交易，不自动下单。",
    "不泄露 token/key。",
    "不使用 git add .。",
    "不 push，等待用户确认。",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_migration_status() -> dict[str, Any]:
    loaded_at = _now_iso()
    long_term_goal_rows = _enrich_long_term_goal_rows([dict(item) for item in LONG_TERM_GOAL_PROGRESS])
    long_term_goal_summary = _build_long_term_goal_summary(long_term_goal_rows)
    tushare_deepseek_linkage_rows = _build_tushare_deepseek_linkage_rows()
    tushare_deepseek_mode_layer_rows = _build_tushare_deepseek_mode_layer_rows()
    tushare_deepseek_linkage_review = _build_tushare_deepseek_linkage_review(
        tushare_deepseek_linkage_rows,
        tushare_deepseek_mode_layer_rows,
    )
    return {
        "packet_key": "command_center_3_migration_status",
        "schema_version": "command_center_3_migration_status.v2",
        "status": "active_migration",
        "mode": "cache_only",
        "loaded_at": loaded_at,
        "progress_baseline": [dict(item) for item in MIGRATION_PROGRESS_BASELINE],
        "long_term_goal_summary": long_term_goal_summary,
        "long_term_goal_rows": long_term_goal_rows,
        "tushare_deepseek_linkage_review": tushare_deepseek_linkage_review,
        "tushare_deepseek_linkage_rows": tushare_deepseek_linkage_rows,
        "tushare_deepseek_mode_layer_rows": tushare_deepseek_mode_layer_rows,
        "target_stack": list(TARGET_STACK),
        "principles": list(MIGRATION_PRINCIPLES),
        "baseline_policy": {
            "use_as_planning_baseline": True,
            "do_not_reestimate_every_turn": True,
            "source": "user_provided_long_term_reference_baseline",
            "long_term_goal_source": "docs/command_center_3_long_term_goals.md",
            "strict_closeout_requires_production_evidence": True,
        },
        "api_policy": {
            "cache_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
            "contains_secret": False,
        },
        "call_ledger": [
            {
                "api": "local_migration_status_cache",
                "endpoint": "GET /api/migration/status",
                "source_type": "user_provided_long_term_reference_baseline",
                "row_count": len(MIGRATION_PROGRESS_BASELINE)
                + len(long_term_goal_rows)
                + len(tushare_deepseek_linkage_rows)
                + len(tushare_deepseek_mode_layer_rows),
                "tushare_deepseek_linkage_row_count": len(tushare_deepseek_linkage_rows),
                "tushare_deepseek_mode_layer_row_count": len(tushare_deepseek_mode_layer_rows),
                "local_fetched_at": loaded_at,
                "call_status": "cache_read",
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
            "GET /api/migration/status 只读展示用户提供的长期迁移基线；不会重新估算、外联或触发任务。",
            "14 个长期目标严格关闭数仍为 0/14；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。",
            "Tushare / DeepSeek 联动按四层审查：cache/render 安静、POST task 门控、task 内真实 provider/model execution、production promotion ledger；真实执行与生产提升仍需后续显式验收。",
            "进度表用于规划判断，不代表自动完成迁移；后续阶段仍需逐项实现和测试。",
        ],
    }
