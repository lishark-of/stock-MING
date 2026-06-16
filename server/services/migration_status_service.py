from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.services import packet_service, task_service


TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE = "run_tushare_deepseek_linkage_review"
TUSHARE_DEEPSEEK_LINKAGE_REVIEW_ROUTE = "POST /api/migration/tushare-deepseek-linkage-review"
TUSHARE_DEEPSEEK_LINKAGE_REVIEW_PACKET_KEY = "command_center_3_migration_status"


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
        "current_state": "freshness gate MVP, local matrix, synthetic long-window replay, local trade_cal artifact audit, provider-acceptance runbook, dry-run scope ticket path, bound execution-request ticket, local SQLite-only producer cache refresh task, next execution recipe, and durable evidence recipe exist.",
        "not_complete_because": "provider-backed long-window trade_cal acceptance and promotion evidence are still pending.",
        "next_step": "Run the dry-run scope ticket, generate a bound execution-request ticket, then execute an explicit provider-backed trade_cal acceptance task when approved and promote only with safe call-ledger and freshness replay evidence.",
        "production_complete": False,
    },
    {
        "id": "LTG-02",
        "goal": "Tushare 全接口生产流水线",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "35%-45%",
        "current_state": "daily / daily_basic / moneyflow light path has real evidence; trade_cal has local dry-run and bound execution-request pre-provider tickets; extended interfaces have matrix, local QA, runbook, dry-run contracts, target-sample execution recipe, a scope-bound target-sample execution-request ticket, latest target-sample request cache visibility, React Data Health target-sample request visibility, production stage-scope manifest, and durable evidence recipe.",
        "not_complete_because": "full-interface provider-backed samples and promotion evidence are incomplete.",
        "next_step": "Use the scope-bound target-sample execution-request ticket to validate future explicit POST provider task runs, starting with trade_cal and then staged market-evidence domains.",
        "production_complete": False,
    },
    {
        "id": "LTG-03",
        "goal": "Factor Test Lab 完整生产化",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "45%-55%",
        "current_state": "IC, Rank IC, ICIR, groups, drawdown, neutralization, split, decay, cost-model scaffolds, local provider blocker receipts, provider small-pool dry-run scope ticket, bound execution-request ticket, provider execution recipe, production stage-scope manifest, and durable evidence recipe exist as research-only/preflight evidence.",
        "not_complete_because": "real provider-backed small-pool validation, safe provider call ledger rows, larger sample coverage, rolling/cost/neutralization/bias evidence, and production research acceptance are still pending.",
        "next_step": "Run a separate user-approved provider-backed small-stock-pool validation bound to the safe scope ticket, execution-request ticket, and execution recipe, then keep every metric outside strategy action.",
        "production_complete": False,
    },
    {
        "id": "LTG-04",
        "goal": "Factor 全市场 / 股票池研究",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "30%-40%",
        "current_state": "watchlist/custom/full-pool contracts, local read-plan receipts, readiness/activation receipts, local rank/zscore sufficiency audit, worker-batch dry-run scope ticket, worker stage-scope manifest, worker-batch execution recipe, bound execution-request ticket, and durable evidence recipe exist.",
        "not_complete_because": "worker-backed batch execution, durable task logs, cross-sectional rank/zscore, neutralization, factor combination research, result persistence, and full-pool validation are pending.",
        "next_step": "Implement a separate explicit worker-backed batch research task bound to the safe scope ticket, execution-request ticket, and execution recipe after storage/worker readiness is stronger.",
        "production_complete": False,
    },
    {
        "id": "LTG-05",
        "goal": "Storage / DuckDB / Parquet 生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "50%-60%",
        "current_state": "schema/version preflight, manifest writer/validator, DuckDB read API, filters, cursor pagination, dry-runs, physical activation receipt, physical stage-scope manifest, physical execution recipe, scope-bound physical execution request ticket, and physical durable evidence recipe exist.",
        "not_complete_because": "physical schema validation evidence, schema migration, partition migration, compaction, TTL refresh execution, cleanup execution, physical task execution, durable evidence promotion, and production promotion remain pending.",
        "next_step": "Run the physical execution recipe one phase at a time from separate explicit physical tasks bound to the request ticket, then promote only with durable evidence rows reviewed; keep no GET writes, no provider refresh from cache, and no data artifacts in git.",
        "production_complete": False,
    },
    {
        "id": "LTG-06",
        "goal": "Worker / Celery / Redis 生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "35%-45%",
        "current_state": "local fallback, task lifecycle, explicit synthetic healthcheck, button-gated activation review task receipts, production evidence plan scope tickets, scope-bound runtime QA execution request tickets, local runtime QA dry-run receipts, runtime QA execution recipe, durable evidence recipe, runtime evidence stage-scope manifest, readiness/activation receipts, scheduler default-off policy, and worker contracts exist.",
        "not_complete_because": "real Celery/Redis process orchestration, broker healthcheck, runtime queue binding, synthetic round-trip dispatch, cross-process control proof, append-only worker log proof, runtime QA task execution, fallback rollback proof, durable evidence promotion, and production scheduler activation are pending; dry-run receipts do not create or execute runtime QA tasks.",
        "next_step": "Run a separate runtime QA task only after manual approval, request-ticket review, and dry-run receipt review, then promote only with durable evidence rows reviewed; keep Celery/Redis start, broker ping, task dispatch, provider/model calls, and scheduler enablement out of cache reads.",
        "production_complete": False,
    },
    {
        "id": "LTG-07",
        "goal": "DeepSeek pro 稳定解释生产化",
        "completion_bucket": "productionization_required",
        "completion_estimate": "35%-45%",
        "current_state": "manual governance, sanitizer, model strategy, JSON stability audit, response-format review, retry/repair dry-run, provider benchmark execution recipe, production stage-scope manifest, durable evidence recipe, and linkage contract exist.",
        "not_complete_because": "JSON stability target, provider-backed benchmark, provider response-format enforcement, bounded retry/repair execution, model ledger/hash dedupe evidence, cost/redaction review, durable evidence promotion, and live_light model execution are pending.",
        "next_step": "Run a larger explicit DeepSeek pro benchmark bound to the execution recipe, then promote only with durable evidence rows reviewed for response_format, retry/repair, ledger hashes, cost, redaction, no numeric/action overwrite, and default-off auto_after_task.",
        "production_complete": False,
    },
    {
        "id": "LTG-08",
        "goal": "ECharts 次日操作图谱成熟版",
        "completion_bucket": "productionization_required",
        "completion_estimate": "45%-55%",
        "current_state": "payload contract, cache envelope, read-only React rendering, reference/zone/position/DeepSeek status, interaction readiness, browser QA runbook, and no-feature-loss legacy parity recipe exist.",
        "not_complete_because": "legacy Streamlit reference capture, browser visual QA, performance trace, no-feature-loss parity evidence, and production replacement promotion are pending.",
        "next_step": "Run explicit same-packet Streamlit parity and browser visual/performance QA without dropping legacy signal groups before retiring the Streamlit visual path.",
        "production_complete": False,
    },
    {
        "id": "LTG-09",
        "goal": "Tauri desktop production package",
        "completion_bucket": "productionization_required",
        "completion_estimate": "30%-40%",
        "current_state": "desktop preflight, runtime contract, backend-offline UX source contract, package QA matrix, release manifest, readiness receipt, durable evidence recipe, blocker audit, and production package stage-scope manifest exist.",
        "not_complete_because": "repeatable tauri dev/build evidence, .app/DMG package QA, packaged runtime QA, backend startup/runtime UX evidence, config/log runtime path validation, signing/notarization, and production release evidence are pending.",
        "next_step": "Run explicit Tauri dev/build and packaged runtime QA only when desktop packaging is the active focus, then promote with durable evidence rows reviewed.",
        "production_complete": False,
    },
    {
        "id": "LTG-10",
        "goal": "Streamlit 完全退出普通主流程",
        "completion_bucket": "dependent_retirement_goal",
        "completion_estimate": "40%-50%",
        "current_state": "Streamlit is marked legacy/admin/debug; primary-workflow exit audit, fallback dependency contract, retirement readiness receipt, durable evidence recipe, and retirement stage-scope manifest exist.",
        "not_complete_because": "React/Tauri ordinary workflow parity, Candidate Radar parity, provider-backed parity, browser/performance QA, admin/debug retention decision, no-feature-cut acceptance, fallback retirement review, and app.py removal-or-retention review are not complete.",
        "next_step": "Run explicit replacement parity and Streamlit fallback retirement reviews only after React/Tauri covers daily workflow, Candidate Radar parity is proven, and fallback blockers are clear.",
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
        "current_state": "research/cache/task/frontend paths keep no-order, no-broker, no-action-mutation, no-real-trade boundaries, release receipt, and trade-isolation stage-scope manifest visible.",
        "not_complete_because": "trade isolation is a permanent release invariant, not a one-time feature that can be closed.",
        "next_step": "Continue proving no real trading and no strategy-action mutation in every new task, provider, model, radar, and UI path.",
        "production_complete": False,
    },
    {
        "id": "LTG-13",
        "goal": "下一票雷达快扫生产化",
        "completion_bucket": "real_validation_required",
        "completion_estimate": "35%-45%",
        "current_state": "local quick-scan readiness, fast-scan task pipeline contract, no-feature-loss QA, legacy parity receipt, full/deep plan receipts, search-to-quant projection receipt, provider parity dry-run ticket, worker execution recipe, scope-bound worker execution-request ticket, scope-bound searched-symbol provider/model execution-request ticket, durable evidence recipe, production stage-scope manifest cache/React visibility, and result-delta clarity exist.",
        "not_complete_because": "async worker execution, real provider-backed radar parity execution, full-pool/deep-scan execution, real searched-symbol provider/model projection execution, DeepSeek model-ledger evidence when enabled, browser performance promotion, legacy retirement review, and durable production replacement evidence are still pending.",
        "next_step": "Use the worker execution-request, quant projection execution-request, and durable evidence recipe to bind real worker full-pool/deep-scan evidence, provider parity call ledger, real Tushare light call ledger, optional DeepSeek model ledger, browser performance/visual proof, and legacy retirement review before any production replacement claim.",
        "production_complete": False,
    },
    {
        "id": "LTG-14",
        "goal": "Command Center 3 动效与可视化清晰度优化",
        "completion_bucket": "later_polish_goal",
        "completion_estimate": "30%-40%",
        "current_state": "motion clarity layer, route/status cues, reduced-motion support, local runner, static QA, activation receipt, promotion dry-run ticket, and durable evidence recipe exist.",
        "not_complete_because": "durable browser visual QA, performance traces, CI/release evidence, and final visual promotion are pending.",
        "next_step": "Use the durable evidence recipe to attach reviewed visual, performance, reduced-motion, and CI/release evidence before any production motion completion claim.",
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
    "LTG-01": ["dry-run scope ticket", "provider trade_cal task", "safe call ledger", "freshness replay", "promotion review"],
    "LTG-02": [
        "scope-bound execution request",
        "provider target samples",
        "full-interface selection",
        "failure-mode evidence",
        "storage promotion",
    ],
    "LTG-03": [
        "scope-bound execution request",
        "provider execution recipe",
        "provider small-pool samples",
        "safe provider call ledger",
        "multi-horizon returns",
        "rolling metrics",
        "cost/neutralization validation",
        "PIT/bias controls",
        "promotion review",
    ],
    "LTG-04": [
        "worker batch execution recipe",
        "worker batch execution",
        "durable task logs",
        "rank/zscore",
        "neutralization",
        "result persistence",
        "full-pool validation",
    ],
    "LTG-05": [
        "physical schema validation",
        "manifest validation evidence",
        "schema/partition migration",
        "compaction",
        "TTL cleanup evidence",
        "durable evidence promotion",
    ],
    "LTG-06": [
        "runtime QA execution",
        "Celery/Redis process evidence",
        "broker healthcheck",
        "queue binding proof",
        "synthetic round-trip dispatch",
        "cross-process control",
        "durable task logs",
        "durable evidence promotion",
    ],
    "LTG-07": [
        "larger provider benchmark",
        "response_format enforcement",
        "retry/repair evidence",
        "model ledger/hash evidence",
        "cost budget",
        "durable evidence promotion",
    ],
    "LTG-08": [
        "same-packet Streamlit parity",
        "no-feature-loss matrix",
        "browser visual QA",
        "performance trace",
        "replacement promotion",
    ],
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

LTG_NEXT_PRIORITY_ORDER = [
    "P0 push gate / local status honesty",
    "P1 LTG-01 trade_cal freshness provider acceptance",
    "P2 LTG-02 Tushare staged provider samples",
    "P3 LTG-03/LTG-13 small-pool factor and radar validation",
    "P4 LTG-05/LTG-06 storage and worker productionization",
    "P5 LTG-07/LTG-08 DeepSeek and ECharts promotion",
    "P6 LTG-09 Tauri package",
    "P7 LTG-10 Streamlit retirement",
    "P8 LTG-14 motion clarity promotion",
]

LTG_NEXT_ACCEPTANCE_ACTION_QUEUE = [
    {
        "queue_id": "p1_trade_cal_provider_acceptance",
        "priority": "P1",
        "ltg_ids": ["LTG-01", "LTG-02"],
        "action_label": "Run user-approved trade_cal provider acceptance",
        "mode_layer": "button_task_then_provider_execution",
        "current_phase": "scope_ticket_and_execution_request_required",
        "first_allowed_route": "POST /api/data-health/trade-cal-provider-acceptance-dry-run",
        "second_allowed_route": "POST /api/data-health/trade-cal-provider-acceptance-execution-request",
        "future_provider_route": "POST /api/tasks/refresh-tushare-facts",
        "target_acceptance_mode": "provider_backed_trade_cal_long_window",
        "required_evidence": [
            "approved dry-run scope hash",
            "bound execution-request ticket",
            "safe Tushare call ledger",
            "730-day trade_cal schema/window evidence",
            "provider-backed freshness replay",
            "promotion review",
        ],
        "not_allowed_next_steps": [
            "call Tushare from GET cache",
            "call Tushare from React render",
            "treat local trade_cal artifact as provider acceptance",
            "mark LTG-01 or LTG-02 complete from a dry-run",
        ],
    },
    {
        "queue_id": "p2_tushare_target_sample_acceptance",
        "priority": "P2",
        "ltg_ids": ["LTG-02"],
        "action_label": "Run staged Tushare target-sample acceptance",
        "mode_layer": "button_task_then_provider_execution",
        "current_phase": "target_sample_execution_request_required",
        "first_allowed_route": "POST /api/tasks/tushare-provider-target-sample-execution-request",
        "second_allowed_route": "",
        "future_provider_route": "POST /api/tasks/refresh-tushare-facts",
        "target_acceptance_mode": "provider_target_sample_acceptance",
        "required_evidence": [
            "selected interface groups",
            "scope-bound execution-request ticket",
            "safe provider call ledger per selected API",
            "row_count/data_date/local_fetched_at/call_status",
            "permission/no_record/empty_window/parse/stale failure-mode rows",
            "storage or no-storage promotion review",
        ],
        "not_allowed_next_steps": [
            "mark unselected APIs verified",
            "treat matrix-only rows as provider acceptance",
            "hide permission or empty-window outcomes",
            "expose token/key material",
        ],
    },
    {
        "queue_id": "p3_factor_small_pool_provider_validation",
        "priority": "P3",
        "ltg_ids": ["LTG-03"],
        "action_label": "Run provider-backed Factor Test Lab small-pool validation",
        "mode_layer": "button_task_then_provider_execution",
        "current_phase": "small_pool_scope_ticket_and_execution_request_required",
        "first_allowed_route": "POST /api/factor-quant/provider-small-pool-dry-run",
        "second_allowed_route": "POST /api/factor-quant/provider-small-pool-execution-request",
        "future_provider_route": "future explicit provider-backed factor validation task",
        "target_acceptance_mode": "provider_backed_factor_small_pool_validation",
        "required_evidence": [
            "approved small-pool scope hash",
            "safe provider call ledger",
            "multi-horizon forward returns",
            "rolling IC/Rank IC/ICIR",
            "cost and turnover evidence",
            "neutralization and PIT/bias controls",
        ],
        "not_allowed_next_steps": [
            "enter strategy action",
            "treat light metrics as production validation",
            "call Tushare from GET cache",
            "turn backtest metrics into trade advice",
        ],
    },
    {
        "queue_id": "p3_candidate_radar_provider_worker_promotion",
        "priority": "P3",
        "ltg_ids": ["LTG-13"],
        "action_label": "Bind Candidate Radar provider/model/worker promotion evidence",
        "mode_layer": "button_task_then_worker_or_provider_execution",
        "current_phase": "promotion_scope_ticket_and_direct_evidence_required",
        "first_allowed_route": "POST /api/candidate-radar/quant-projection-acceptance-dry-run",
        "second_allowed_route": "POST /api/candidate-radar/quant-projection-execution-request",
        "future_provider_route": "future explicit worker/provider/model radar execution tasks",
        "target_acceptance_mode": "provider_worker_backed_radar_replacement",
        "required_evidence": [
            "legacy no-feature-loss parity",
            "real Tushare light call ledger",
            "optional DeepSeek model ledger when enabled",
            "worker full-pool/deep-scan evidence",
            "browser performance and visual proof",
            "legacy retirement review",
        ],
        "not_allowed_next_steps": [
            "run full-pool/deep-scan from render",
            "hide provider or freshness gaps",
            "generate buy/sell candidates from local-only evidence",
            "retire legacy radar before parity evidence",
        ],
    },
]

LTG_NEXT_ACCEPTANCE_ACTION_OBSERVATION_STEPS = {
    "p1_trade_cal_provider_acceptance": [
        {
            "phase_key": "trade_cal_dry_run_scope_ticket",
            "task_type": "run_trade_cal_provider_acceptance_dry_run",
            "receipt_key": "trade_cal_provider_acceptance_dry_run_receipt",
            "route": "POST /api/data-health/trade-cal-provider-acceptance-dry-run",
        },
        {
            "phase_key": "trade_cal_execution_request_ticket",
            "task_type": "run_trade_cal_provider_acceptance_execution_request",
            "receipt_key": "trade_cal_provider_acceptance_execution_request_receipt",
            "route": "POST /api/data-health/trade-cal-provider-acceptance-execution-request",
        },
        {
            "phase_key": "trade_cal_promotion_review_receipt",
            "task_type": "run_trade_cal_provider_acceptance_promotion_review",
            "receipt_key": "trade_cal_provider_acceptance_promotion_review_receipt",
            "route": "POST /api/data-health/trade-cal-provider-acceptance-promotion-review",
        },
    ],
    "p2_tushare_target_sample_acceptance": [
        {
            "phase_key": "target_sample_execution_request_ticket",
            "task_type": "run_tushare_provider_target_sample_execution_request",
            "receipt_key": "provider_target_sample_execution_request_receipt",
            "route": "POST /api/tasks/tushare-provider-target-sample-execution-request",
        },
    ],
    "p3_factor_small_pool_provider_validation": [
        {
            "phase_key": "factor_small_pool_dry_run_scope_ticket",
            "task_type": "run_factor_test_provider_small_pool_acceptance_dry_run",
            "receipt_key": "provider_small_pool_acceptance_dry_run_receipt",
            "route": "POST /api/factor-quant/provider-small-pool-dry-run",
        },
        {
            "phase_key": "factor_small_pool_execution_request_ticket",
            "task_type": "run_factor_test_provider_small_pool_execution_request",
            "receipt_key": "provider_small_pool_execution_request_receipt",
            "route": "POST /api/factor-quant/provider-small-pool-execution-request",
        },
    ],
    "p3_candidate_radar_provider_worker_promotion": [
        {
            "phase_key": "radar_quant_projection_dry_run_scope_ticket",
            "task_type": "run_candidate_radar_quant_projection_acceptance_dry_run",
            "receipt_key": "search_quant_projection_acceptance_dry_run_receipt",
            "route": "POST /api/candidate-radar/quant-projection-acceptance-dry-run",
        },
        {
            "phase_key": "radar_quant_projection_execution_request_ticket",
            "task_type": "run_candidate_radar_quant_projection_execution_request",
            "receipt_key": "search_quant_projection_execution_request_receipt",
            "route": "POST /api/candidate-radar/quant-projection-execution-request",
        },
        {
            "phase_key": "radar_production_promotion_dry_run_ticket",
            "task_type": "run_candidate_radar_production_promotion_dry_run",
            "receipt_key": "candidate_radar_production_promotion_dry_run_receipt",
            "route": "POST /api/candidate-radar/production-promotion-dry-run",
        },
    ],
}


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
    goal_count = len(rows)
    production_complete_count = sum(1 for row in rows if row.get("production_complete") is True)
    stage_scope_manifest_count = sum(1 for row in rows if row.get("has_stage_scope_manifest") is True)
    observed_stage_scope_manifest_count = sum(
        1 for row in rows if row.get("observed_stage_scope_manifest_status")
    )
    observed_stage_scope_pending_count = sum(
        int(row.get("observed_stage_scope_pending_count") or 0)
        for row in rows
        if row.get("observed_stage_scope_manifest_status")
    )
    return {
        "goal_count": goal_count,
        "closed_count": production_complete_count,
        "production_complete_count": production_complete_count,
        "strict_closeout": f"{production_complete_count}/{goal_count}",
        "strict_closeout_done_count": production_complete_count,
        "strict_closeout_total_count": goal_count,
        "strict_closeout_remaining_count": goal_count - production_complete_count,
        "strict_closeout_can_close_from_local_contracts": False,
        "stage_scope_manifest_count": stage_scope_manifest_count,
        "stage_scope_manifest_pending_count": sum(
            1 for row in rows if row.get("stage_scope_manifest_status") == "present_pending_production_evidence"
        ),
        "observed_stage_scope_manifest_count": observed_stage_scope_manifest_count,
        "observed_stage_scope_pending_count": observed_stage_scope_pending_count,
        "goals_with_next_evidence_count": sum(1 for row in rows if int(row.get("next_evidence_required_count") or 0) > 0),
        "can_close_from_local_contracts_count": sum(
            1 for row in rows if row.get("can_close_from_local_contracts") is True
        ),
        "foundation_progress_estimate": "about_70_percent",
        "production_acceptance_estimate": "about_25_to_35_percent",
        "bucket_counts": bucket_counts,
        "bucket_meanings": dict(LONG_TERM_GOAL_BUCKETS),
        "next_priority_order": list(LTG_NEXT_PRIORITY_ORDER),
        "no_goal_may_close_from": ["scaffold", "preflight", "mock", "matrix", "sanitizer", "dry_run", "local_receipt"],
    }


def _build_ltg_acceptance_runway_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runway_rows: list[dict[str, Any]] = []
    for row in rows:
        goal_id = str(row.get("id") or "")
        priority = next((item for item in LTG_NEXT_PRIORITY_ORDER if goal_id in item), "ongoing")
        runway_rows.append(
            {
                "id": goal_id,
                "priority": priority,
                "goal": row.get("goal"),
                "bucket": row.get("completion_bucket"),
                "completion_estimate": row.get("completion_estimate"),
                "observed_pending": int(row.get("observed_stage_scope_pending_count") or 0),
                "next_step": row.get("next_step"),
                "can_close_goal": False,
                "production_complete": row.get("production_complete") is True,
                "observed_stage_scope_manifest_status": row.get("observed_stage_scope_manifest_status"),
                "next_evidence_required_count": int(row.get("next_evidence_required_count") or 0),
                "source": "long_term_goal_rows_and_ltg_stage_scope_observed_rows",
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "evidence_boundary": "acceptance_runway_is_planning_surface_not_production_completion",
            }
        )
    return runway_rows


def _task_statuses_by_type() -> dict[str, list[dict[str, Any]]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for task in task_service.list_task_statuses():
        task_type = str(task.get("task_type") or "")
        if task_type:
            by_type.setdefault(task_type, []).append(task)
    return by_type


def _receipt_blocker_count(receipt: dict[str, Any]) -> int:
    blocker_keys = (
        "blocking_row_count",
        "blocking_phase_count",
        "local_blocker_count",
        "production_blocker_count",
        "provider_evidence_blocker_count",
        "credential_missing_provider_count",
        "durable_evidence_blocker_count",
    )
    return max((int(receipt.get(key) or 0) for key in blocker_keys), default=0)


def _receipt_target_payload_safe_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    payload = receipt.get("target_payload_safe") if isinstance(receipt.get("target_payload_safe"), dict) else {}
    payload_map = payload if isinstance(payload, dict) else {}
    return {
        "target_payload_present": bool(payload_map),
        "target_payload_apis": [str(item) for item in payload_map.get("apis") or [] if str(item or "")],
        "target_payload_groups": [
            str(item) for item in payload_map.get("target_sample_acceptance_groups") or [] if str(item or "")
        ],
        "target_payload_acceptance_mode": str(payload_map.get("acceptance_mode") or receipt.get("target_acceptance_mode") or ""),
        "target_payload_ts_code": str(payload_map.get("ts_code") or ""),
        "target_payload_trade_date": str(payload_map.get("trade_date") or ""),
        "target_payload_start_date": str(payload_map.get("start_date") or ""),
        "target_payload_end_date": str(payload_map.get("end_date") or ""),
        "target_payload_provider_execution_requires_separate_post_task": bool(
            payload_map.get("provider_execution_requires_separate_post_task")
        ),
    }


def _receipt_local_ready(receipt: dict[str, Any]) -> bool:
    ready_keys = (
        "local_dry_run_ready",
        "local_execution_request_ready",
        "ready_for_local_promotion_review",
        "promotion_review_ready_for_release",
        "recipe_ready_for_user_confirmation",
        "ready_for_manual_provider_task_submission",
        "ready_for_manual_worker_task_submission",
        "ready_for_manual_provider_model_task_submission",
    )
    if any(receipt.get(key) is True for key in ready_keys):
        return True
    ready_statuses = {
        "trade_cal_acceptance_dry_run_ready_real_execution_still_blocked",
    }
    return str(receipt.get("status") or "") in ready_statuses


def _build_ltg_next_action_local_step_rows(
    queue_id: str,
    tasks_by_type: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    step_rows: list[dict[str, Any]] = []
    for step in LTG_NEXT_ACCEPTANCE_ACTION_OBSERVATION_STEPS.get(queue_id, []):
        task_type = str(step["task_type"])
        latest_task = next(iter(tasks_by_type.get(task_type, [])), {})
        payload_safe = latest_task.get("payload_safe") if isinstance(latest_task.get("payload_safe"), dict) else {}
        receipt = payload_safe.get(str(step["receipt_key"])) if isinstance(payload_safe, dict) else {}
        receipt_map = receipt if isinstance(receipt, dict) else {}
        receipt_scope_hash = str(
            receipt_map.get("acceptance_scope_hash")
            or receipt_map.get("review_scope_hash")
            or receipt_map.get("production_replacement_review_scope_hash")
            or ""
        )
        receipt_scope_hash_short = str(
            receipt_map.get("acceptance_scope_hash_short")
            or receipt_map.get("review_scope_hash_short")
            or receipt_map.get("production_replacement_review_scope_hash_short")
            or (receipt_scope_hash[:16] if receipt_scope_hash else "")
        )
        task_found = bool(latest_task)
        receipt_visible = bool(receipt_map)
        latest_task_storage_source = str(latest_task.get("storage_source") or "") if task_found else ""
        receipt_durable_in_sqlite = bool(
            receipt_visible and latest_task_storage_source in {"memory_and_sqlite", "sqlite_meta"}
        )
        receipt_memory_only = bool(receipt_visible and latest_task_storage_source == "memory")
        if not receipt_visible:
            receipt_durability_state = "receipt_missing"
        elif receipt_durable_in_sqlite:
            receipt_durability_state = "durable_sqlite_receipt_visible"
        elif receipt_memory_only:
            receipt_durability_state = "memory_only_receipt_visible"
        else:
            receipt_durability_state = "receipt_visible_without_sqlite_durability"
        target_payload_summary = _receipt_target_payload_safe_summary(receipt_map) if receipt_visible else {}
        local_ready = _receipt_local_ready(receipt_map) if receipt_visible else False
        step_rows.append(
            {
                "phase_key": step["phase_key"],
                "task_type": task_type,
                "route": step["route"],
                "task_found": task_found,
                "receipt_visible": receipt_visible,
                "latest_task_id": latest_task.get("task_id") if task_found else "",
                "latest_task_status": latest_task.get("status") if task_found else "",
                "latest_task_current_step": latest_task.get("current_step") if task_found else "",
                "latest_task_storage_source": latest_task_storage_source,
                "receipt_durable_in_sqlite": receipt_durable_in_sqlite,
                "receipt_memory_only": receipt_memory_only,
                "receipt_durability_state": receipt_durability_state,
                "receipt_durable_required_for_handoff": receipt_visible,
                "receipt_status": receipt_map.get("status") or "",
                "receipt_scope_hash": receipt_scope_hash,
                "receipt_scope_hash_short": receipt_scope_hash_short,
                "receipt_blocker_count": _receipt_blocker_count(receipt_map) if receipt_visible else 0,
                "receipt_target_post_task_route": receipt_map.get("target_post_task_route") or "",
                "receipt_target_task_type": receipt_map.get("target_task_type") or "",
                "receipt_target_acceptance_mode": receipt_map.get("target_acceptance_mode") or "",
                "receipt_target_payload_present": target_payload_summary.get("target_payload_present") is True,
                "receipt_target_payload_apis": target_payload_summary.get("target_payload_apis") or [],
                "receipt_target_payload_groups": target_payload_summary.get("target_payload_groups") or [],
                "receipt_target_payload_acceptance_mode": (
                    target_payload_summary.get("target_payload_acceptance_mode") or ""
                ),
                "receipt_target_payload_ts_code": target_payload_summary.get("target_payload_ts_code") or "",
                "receipt_target_payload_trade_date": target_payload_summary.get("target_payload_trade_date") or "",
                "receipt_target_payload_start_date": target_payload_summary.get("target_payload_start_date") or "",
                "receipt_target_payload_end_date": target_payload_summary.get("target_payload_end_date") or "",
                "receipt_target_payload_provider_execution_requires_separate_post_task": (
                    target_payload_summary.get("target_payload_provider_execution_requires_separate_post_task") is True
                ),
                "receipt_ready_for_manual_provider_task_submission": (
                    receipt_map.get("ready_for_manual_provider_task_submission") is True
                ),
                "receipt_creates_provider_task": receipt_map.get("creates_provider_task") is True,
                "receipt_provider_task_created": receipt_map.get("provider_task_created") is True,
                "receipt_provider_execution_implemented": receipt_map.get("provider_execution_implemented") is True,
                "local_ready": local_ready,
                "local_blocked": bool(receipt_visible and not local_ready),
                "creates_task_from_lookup": False,
                "lookup_calls_provider": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "evidence_boundary": "latest_local_receipt_lookup_is_not_provider_or_worker_execution",
            }
        )
    return step_rows


def _local_step_row_by_phase(local_step_rows: list[dict[str, Any]], phase_key: str) -> dict[str, Any]:
    return next((row for row in local_step_rows if row.get("phase_key") == phase_key), {})


def _latest_tushare_target_sample_execution_recipe_preview() -> dict[str, Any]:
    try:
        packet = packet_service.read_packet("command_center_tushare_refresh_packet")
    except Exception:
        packet = {}
    recipe = packet.get("provider_target_sample_execution_recipe") if isinstance(packet, dict) else {}
    recipe_map = recipe if isinstance(recipe, dict) else {}
    rows = [row for row in recipe_map.get("rows", []) if isinstance(row, dict)]
    selected_apis: list[str] = []
    for row in rows:
        if row.get("requested_for_execution_recipe") is not True:
            continue
        for api in row.get("selected_apis") or []:
            api_name = str(api or "")
            if api_name and api_name not in selected_apis:
                selected_apis.append(api_name)
    requested_targets = [str(item) for item in recipe_map.get("requested_targets") or [] if str(item or "")]
    scope_hash_short = str(recipe_map.get("execution_recipe_scope_hash_short") or "")[:16]
    recipe_visible = bool(recipe_map)
    recipe_ready = bool(
        recipe_map.get("schema_version") == "tushare_provider_target_sample_execution_recipe.v1"
        and recipe_map.get("status") == "target_sample_execution_recipe_ready_user_confirmation_required"
        and recipe_map.get("recipe_ready_for_user_confirmation") is True
        and recipe_map.get("provider_task_created_by_recipe") is False
        and recipe_map.get("provider_execution_implemented_by_recipe") is False
        and recipe_map.get("recipe_external_calls_triggered") is False
        and recipe_map.get("tushare_called_by_recipe") is False
        and recipe_map.get("deepseek_called") is False
        and recipe_map.get("github_called") is False
        and recipe_map.get("does_not_execute_trades") is True
        and recipe_map.get("does_not_modify_strategy_action") is True
        and recipe_map.get("contains_secret") is False
        and bool(scope_hash_short)
        and bool(requested_targets)
        and bool(selected_apis)
    )
    return {
        "recipe_visible": recipe_visible,
        "recipe_status": str(recipe_map.get("status") or ""),
        "recipe_ready_for_user_confirmation": recipe_ready,
        "execution_recipe_scope_hash_short": scope_hash_short,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "can_prebind_execution_recipe_scope_hash": recipe_ready,
        "source_packet_key": "command_center_tushare_refresh_packet",
        "source_receipt_key": "provider_target_sample_execution_recipe",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_boundary": "latest_target_sample_recipe_preview_is_read_only_not_provider_execution",
    }


def _build_ltg_next_action_submission_preview_rows(
    next_local_step: str,
    local_step_rows: list[dict[str, Any]],
    safe_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    safe_context = dict(safe_context or {})
    route_specs: dict[str, dict[str, Any]] = {
        "POST /api/data-health/trade-cal-provider-acceptance-dry-run": {
            "step_kind": "dry_run_scope_ticket",
            "safe_payload_summary": "approved_by_user, apis=trade_cal, exchange=SSE/SZSE, rolling_730_day_window",
            "expected_local_receipt": "trade_cal_provider_acceptance_dry_run_receipt",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/data-health/trade-cal-provider-acceptance-execution-request": {
            "step_kind": "scope_bound_execution_request",
            "safe_payload_summary": "approved_by_user plus latest trade_cal dry-run scope hash",
            "expected_local_receipt": "trade_cal_provider_acceptance_execution_request_receipt",
            "required_prior_phase_key": "trade_cal_dry_run_scope_ticket",
            "required_prior_material": "receipt_scope_hash_short",
        },
        "POST /api/data-health/trade-cal-provider-acceptance-promotion-review": {
            "step_kind": "local_promotion_review",
            "safe_payload_summary": "approved_by_user plus latest execution-request task id",
            "expected_local_receipt": "trade_cal_provider_acceptance_promotion_review_receipt",
            "required_prior_phase_key": "trade_cal_execution_request_ticket",
            "required_prior_material": "latest_task_id",
        },
        "POST /api/tasks/tushare-provider-target-sample-execution-request": {
            "step_kind": "manual_scope_bound_execution_request",
            "safe_payload_summary": "operator_approved, selected target sample APIs, ts_code, and execution_recipe_scope_hash",
            "expected_local_receipt": "provider_target_sample_execution_request_receipt",
            "required_prior_phase_key": "provider_target_sample_execution_recipe",
            "required_prior_material": "execution_recipe_scope_hash",
            "manual_scope_hash_required": True,
            "context_key": "tushare_target_sample_execution_recipe_preview",
        },
        "POST /api/factor-quant/provider-small-pool-dry-run": {
            "step_kind": "dry_run_scope_ticket",
            "safe_payload_summary": "approved_by_user, explicit small symbol pool, research metrics, forward-return horizons",
            "expected_local_receipt": "provider_small_pool_acceptance_dry_run_receipt",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/factor-quant/provider-small-pool-execution-request": {
            "step_kind": "scope_bound_execution_request",
            "safe_payload_summary": "approved_by_user plus latest Factor small-pool dry-run scope hash",
            "expected_local_receipt": "provider_small_pool_execution_request_receipt",
            "required_prior_phase_key": "factor_small_pool_dry_run_scope_ticket",
            "required_prior_material": "receipt_scope_hash",
        },
        "POST /api/candidate-radar/quant-projection-acceptance-dry-run": {
            "step_kind": "dry_run_scope_ticket",
            "safe_payload_summary": "symbol, selected light APIs, include_tushare/include_deepseek booleans, user approval",
            "expected_local_receipt": "search_quant_projection_acceptance_dry_run_receipt",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/candidate-radar/quant-projection-execution-request": {
            "step_kind": "scope_bound_execution_request",
            "safe_payload_summary": "operator_approved plus latest radar quant-projection dry-run scope hash",
            "expected_local_receipt": "search_quant_projection_execution_request_receipt",
            "required_prior_phase_key": "radar_quant_projection_dry_run_scope_ticket",
            "required_prior_material": "receipt_scope_hash",
        },
        "POST /api/candidate-radar/production-promotion-dry-run": {
            "step_kind": "manual_scope_bound_promotion_dry_run",
            "safe_payload_summary": "operator_approved plus latest production replacement review scope hash",
            "expected_local_receipt": "candidate_radar_production_promotion_dry_run_receipt",
            "required_prior_phase_key": "candidate_radar_production_replacement_review_receipt",
            "required_prior_material": "review_scope_hash",
            "manual_scope_hash_required": True,
        },
    }
    spec = route_specs.get(next_local_step)
    if spec is None:
        return [
            {
                "next_local_step": next_local_step,
                "step_kind": "future_provider_or_worker_evidence",
                "local_button_available": False,
                "ready_for_clean_local_receipt": False,
                "disabled_reason": "route_is_not_an_allowlisted_local_receipt_step",
                "safe_payload_summary": "",
                "required_prior_phase_key": "",
                "required_prior_material": "",
                "required_prior_receipt_visible": False,
                "required_prior_material_visible": False,
                "manual_scope_hash_required": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "evidence_boundary": "submission_preview_is_read_only_not_task_execution",
            }
        ]

    required_phase = str(spec.get("required_prior_phase_key") or "")
    required_material = str(spec.get("required_prior_material") or "")
    context_key = str(spec.get("context_key") or "")
    context = safe_context.get(context_key) if context_key else {}
    context_map = context if isinstance(context, dict) else {}
    prior_step = _local_step_row_by_phase(local_step_rows, required_phase) if required_phase else {}
    prior_visible = True if not required_phase else bool(prior_step.get("receipt_visible"))
    if not required_material:
        material_visible = True
    elif required_material == "latest_task_id":
        material_visible = bool(prior_step.get("latest_task_id"))
    else:
        material_visible = bool(
            prior_step.get(required_material)
            or prior_step.get("receipt_scope_hash")
            or prior_step.get("receipt_scope_hash_short")
        )
    manual_scope_hash_required = bool(spec.get("manual_scope_hash_required"))
    if context_key == "tushare_target_sample_execution_recipe_preview":
        prior_visible = bool(context_map.get("recipe_visible"))
        material_visible = bool(context_map.get("execution_recipe_scope_hash_short"))
        manual_scope_hash_required = not bool(context_map.get("can_prebind_execution_recipe_scope_hash"))
    ready_for_clean_receipt = prior_visible and material_visible and not manual_scope_hash_required
    if ready_for_clean_receipt:
        disabled_reason = ""
    elif context_key == "tushare_target_sample_execution_recipe_preview" and not prior_visible:
        disabled_reason = "latest_target_sample_execution_recipe_missing"
    elif context_key == "tushare_target_sample_execution_recipe_preview" and prior_visible and manual_scope_hash_required:
        disabled_reason = "latest_target_sample_execution_recipe_not_ready_for_confirmation"
    elif manual_scope_hash_required:
        disabled_reason = "manual_scope_hash_required_before_clean_local_receipt"
    elif not prior_visible:
        disabled_reason = "required_prior_local_receipt_missing"
    else:
        disabled_reason = "required_prior_material_missing"
    return [
        {
            "next_local_step": next_local_step,
            "step_kind": spec["step_kind"],
            "local_button_available": True,
            "ready_for_clean_local_receipt": ready_for_clean_receipt,
            "disabled_reason": disabled_reason,
            "safe_payload_summary": spec["safe_payload_summary"],
            "expected_local_receipt": spec["expected_local_receipt"],
            "required_prior_phase_key": required_phase,
            "required_prior_material": required_material,
            "required_prior_receipt_visible": prior_visible,
            "required_prior_material_visible": material_visible,
            "manual_scope_hash_required": manual_scope_hash_required,
            "prepared_execution_recipe_scope_hash_short": context_map.get("execution_recipe_scope_hash_short") or "",
            "prepared_target_sample_acceptance_groups": list(context_map.get("requested_targets") or []),
            "prepared_apis": list(context_map.get("selected_apis") or []),
            "prepared_context_status": context_map.get("recipe_status") or "",
            "prepared_context_source_packet_key": context_map.get("source_packet_key") or "",
            "prepared_context_source_receipt_key": context_map.get("source_receipt_key") or "",
            "would_create_provider_task": False,
            "would_start_worker": False,
            "would_call_model": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "can_close_goal": False,
            "production_complete": False,
            "evidence_boundary": "submission_preview_is_read_only_not_task_execution",
        }
    ]


def _build_ltg_future_handoff_preview_rows(
    next_local_step: str,
    local_step_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest_ready_step = next(
        (
            row
            for row in reversed(local_step_rows)
            if row.get("receipt_visible") is True and row.get("receipt_ready_for_manual_provider_task_submission") is True
        ),
        {},
    )
    route = str(
        latest_ready_step.get("receipt_target_post_task_route")
        or (next_local_step if next_local_step.startswith("POST /api/") else "")
    )
    durable_local_receipt = latest_ready_step.get("receipt_durable_in_sqlite") is True
    handoff_ready = bool(
        latest_ready_step
        and durable_local_receipt
        and latest_ready_step.get("receipt_target_payload_present") is True
        and latest_ready_step.get("receipt_creates_provider_task") is False
        and latest_ready_step.get("receipt_provider_task_created") is False
        and latest_ready_step.get("receipt_provider_execution_implemented") is False
    )
    if handoff_ready:
        status = "future_provider_handoff_preview_ready"
        disabled_reason = ""
    elif latest_ready_step and not durable_local_receipt:
        status = "future_provider_handoff_waiting_for_durable_local_receipt"
        disabled_reason = "local_execution_request_receipt_not_durable_in_sqlite"
    elif any(row.get("receipt_visible") for row in local_step_rows):
        status = "future_provider_handoff_waiting_for_ready_execution_request"
        disabled_reason = "latest_local_receipt_not_ready_for_provider_handoff"
    else:
        status = "future_provider_handoff_waiting_for_local_receipt"
        disabled_reason = "local_execution_request_receipt_missing"
    return [
        {
            "status": status,
            "future_route": route,
            "future_task_type": latest_ready_step.get("receipt_target_task_type") or "",
            "target_acceptance_mode": latest_ready_step.get("receipt_target_acceptance_mode") or "",
            "target_payload_apis": latest_ready_step.get("receipt_target_payload_apis") or [],
            "target_payload_groups": latest_ready_step.get("receipt_target_payload_groups") or [],
            "target_payload_ts_code": latest_ready_step.get("receipt_target_payload_ts_code") or "",
            "target_payload_trade_date": latest_ready_step.get("receipt_target_payload_trade_date") or "",
            "target_payload_start_date": latest_ready_step.get("receipt_target_payload_start_date") or "",
            "target_payload_end_date": latest_ready_step.get("receipt_target_payload_end_date") or "",
            "source_local_phase_key": latest_ready_step.get("phase_key") or "",
            "source_local_task_id": latest_ready_step.get("latest_task_id") or "",
            "source_local_receipt_status": latest_ready_step.get("receipt_status") or "",
            "source_local_storage_source": latest_ready_step.get("latest_task_storage_source") or "",
            "source_local_receipt_durable_in_sqlite": durable_local_receipt,
            "source_local_receipt_memory_only": latest_ready_step.get("receipt_memory_only") is True,
            "durable_local_receipt_required_for_handoff": True,
            "handoff_ready_from_local_receipt": handoff_ready,
            "disabled_reason": disabled_reason,
            "creates_provider_task_from_preview": False,
            "provider_task_created_by_preview": False,
            "provider_execution_implemented_by_preview": False,
            "requires_separate_user_approved_provider_task": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "can_close_goal": False,
            "production_complete": False,
            "evidence_boundary": "future_handoff_preview_is_read_only_not_provider_execution",
        }
    ]


def _build_ltg_next_acceptance_action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("id") or ""): row for row in rows}
    tasks_by_type = _task_statuses_by_type()
    action_rows: list[dict[str, Any]] = []
    for index, action in enumerate(LTG_NEXT_ACCEPTANCE_ACTION_QUEUE, start=1):
        ltg_ids = [str(item) for item in action["ltg_ids"]]
        linked_rows = [rows_by_id[goal_id] for goal_id in ltg_ids if goal_id in rows_by_id]
        local_step_rows = _build_ltg_next_action_local_step_rows(str(action["queue_id"]), tasks_by_type)
        observed_steps = [row for row in local_step_rows if row["receipt_visible"] is True]
        missing_steps = [row for row in local_step_rows if row["receipt_visible"] is False]
        ready_steps = [row for row in local_step_rows if row.get("receipt_visible") is True and row.get("local_ready") is True]
        blocked_steps = [
            row for row in local_step_rows if row.get("receipt_visible") is True and row.get("local_ready") is not True
        ]
        first_not_ready_step = next(
            (row for row in local_step_rows if not (row.get("receipt_visible") is True and row.get("local_ready") is True)),
            {},
        )
        durable_observed_steps = [row for row in observed_steps if row.get("receipt_durable_in_sqlite") is True]
        memory_only_observed_steps = [row for row in observed_steps if row.get("receipt_memory_only") is True]
        if not local_step_rows:
            local_status = "local_receipt_lookup_not_configured"
            next_local_step = ""
        elif not observed_steps:
            local_status = "local_receipts_missing"
            next_local_step = str(first_not_ready_step.get("route") or "")
        elif blocked_steps:
            local_status = "local_receipts_visible_but_blocked"
            next_local_step = str(first_not_ready_step.get("route") or "")
        elif missing_steps:
            local_status = "local_receipts_partially_visible_next_step_pending"
            next_local_step = str(first_not_ready_step.get("route") or "")
        else:
            local_status = "local_receipts_visible_provider_or_worker_evidence_pending"
            next_local_step = str(action["future_provider_route"])
        latest_observed = observed_steps[-1] if observed_steps else {}
        safe_context: dict[str, Any] = {}
        if action["queue_id"] == "p2_tushare_target_sample_acceptance":
            safe_context["tushare_target_sample_execution_recipe_preview"] = (
                _latest_tushare_target_sample_execution_recipe_preview()
            )
        submission_preview_rows = _build_ltg_next_action_submission_preview_rows(
            next_local_step,
            local_step_rows,
            safe_context=safe_context,
        )
        future_handoff_preview_rows = _build_ltg_future_handoff_preview_rows(next_local_step, local_step_rows)
        next_step_ready_for_clean_receipt = any(
            row.get("ready_for_clean_local_receipt") is True for row in submission_preview_rows
        )
        next_step_disabled_reason = next(
            (str(row.get("disabled_reason") or "") for row in submission_preview_rows if row.get("disabled_reason")),
            "",
        )
        future_handoff_ready = any(
            row.get("handoff_ready_from_local_receipt") is True for row in future_handoff_preview_rows
        )
        action_rows.append(
            {
                "queue_order": index,
                "queue_id": action["queue_id"],
                "priority": action["priority"],
                "ltg_ids": ltg_ids,
                "linked_goal_count": len(linked_rows),
                "action_label": action["action_label"],
                "mode_layer": action["mode_layer"],
                "current_phase": action["current_phase"],
                "first_allowed_route": action["first_allowed_route"],
                "second_allowed_route": action["second_allowed_route"],
                "future_provider_route": action["future_provider_route"],
                "target_acceptance_mode": action["target_acceptance_mode"],
                "required_evidence": list(action["required_evidence"]),
                "required_evidence_count": len(action["required_evidence"]),
                "not_allowed_next_steps": list(action["not_allowed_next_steps"]),
                "not_allowed_next_step_count": len(action["not_allowed_next_steps"]),
                "local_receipt_status": local_status,
                "next_local_step": next_local_step,
                "local_receipt_step_count": len(local_step_rows),
                "observed_local_receipt_step_count": len(observed_steps),
                "missing_local_receipt_step_count": len(missing_steps),
                "ready_local_receipt_step_count": len(ready_steps),
                "blocked_local_receipt_step_count": len(blocked_steps),
                "durable_local_receipt_step_count": len(durable_observed_steps),
                "memory_only_local_receipt_step_count": len(memory_only_observed_steps),
                "local_receipts_all_durable": bool(observed_steps)
                and len(durable_observed_steps) == len(observed_steps),
                "local_receipts_require_sqlite_durability_for_handoff": True,
                "observed_local_receipt_steps": [str(row.get("phase_key") or "") for row in observed_steps],
                "missing_local_receipt_steps": [str(row.get("phase_key") or "") for row in missing_steps],
                "ready_local_receipt_steps": [str(row.get("phase_key") or "") for row in ready_steps],
                "blocked_local_receipt_steps": [str(row.get("phase_key") or "") for row in blocked_steps],
                "latest_observed_task_id": latest_observed.get("latest_task_id") or "",
                "latest_observed_task_type": latest_observed.get("task_type") or "",
                "latest_observed_receipt_status": latest_observed.get("receipt_status") or "",
                "local_receipt_blocker_count": sum(int(row.get("receipt_blocker_count") or 0) for row in observed_steps),
                "local_step_rows": local_step_rows,
                "next_local_step_preview_rows": submission_preview_rows,
                "next_local_step_preview_row_count": len(submission_preview_rows),
                "next_local_step_ready_for_clean_receipt": next_step_ready_for_clean_receipt,
                "next_local_step_disabled_reason": next_step_disabled_reason,
                "future_handoff_preview_rows": future_handoff_preview_rows,
                "future_handoff_preview_row_count": len(future_handoff_preview_rows),
                "future_handoff_ready_from_local_receipt": future_handoff_ready,
                "local_receipt_lookup_source": "task_service.list_task_statuses_memory_plus_sqlite_read_only",
                "local_receipt_lookup_creates_task": False,
                "local_receipt_lookup_calls_provider": False,
                "max_linked_observed_pending": max(
                    (int(row.get("observed_stage_scope_pending_count") or 0) for row in linked_rows),
                    default=0,
                ),
                "linked_completion_estimates": [
                    f"{row.get('id')}:{row.get('completion_estimate')}" for row in linked_rows
                ],
                "linked_buckets": [str(row.get("completion_bucket") or "") for row in linked_rows],
                "requires_explicit_user_confirmation": True,
                "creates_task_from_get": False,
                "creates_task_from_render": False,
                "cache_only": True,
                "provider_execution_implemented": False,
                "model_execution_implemented": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_goal": False,
                "production_complete": False,
                "evidence_boundary": "next_acceptance_action_queue_is_read_only_not_task_execution",
            }
        )
    return action_rows


def _build_ltg_stage_scope_observed_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from scripts import data_health_freshness_contract

        stage_rows = data_health_freshness_contract._freshness_production_stage_scope_rows()
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_freshness_gate_complete") is False
        )
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-01",
                "goal": "A 股交易日历级 freshness 生产化",
                "stage_scope_manifest": "freshness_production_stage_scope_manifest",
                "status": "observed_in_data_health_freshness_static_contract"
                if stage_rows
                else "missing_from_data_health_freshness_static_contract",
                "observed_source": "scripts/data_health_freshness_contract._freshness_production_stage_scope_rows local static contract",
                "cache_status": "data_health_freshness_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "provider_backed_trade_cal_acceptance_done": False,
                "production_freshness_gate_complete": False,
                "real_trade_cal_long_window_validation_done": False,
                "provider_refresh_called_by_contract": False,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "freshness_replay_provider_evidence_done": False,
                "failure_mode_provider_evidence_done": False,
                "current_evidence_producer_coverage_complete": False,
                "decision_surface_mutated_by_contract": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_freshness_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-01",
                "goal": "A 股交易日历级 freshness 生产化",
                "stage_scope_manifest": "freshness_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/data_health_freshness_contract._freshness_production_stage_scope_rows local static contract",
                "error_message_safe": "freshness_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "provider_backed_trade_cal_acceptance_done": False,
                "production_freshness_gate_complete": False,
                "real_trade_cal_long_window_validation_done": False,
                "provider_refresh_called_by_contract": False,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "freshness_replay_provider_evidence_done": False,
                "failure_mode_provider_evidence_done": False,
                "current_evidence_producer_coverage_complete": False,
                "decision_surface_mutated_by_contract": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import tushare_acceptance_contract

        stage_rows = tushare_acceptance_contract._tushare_production_stage_scope_rows()
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_tushare_pipeline_complete") is False
        )
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-02",
                "goal": "Tushare 全接口生产流水线",
                "stage_scope_manifest": "tushare_production_stage_scope_manifest",
                "status": "observed_in_tushare_acceptance_static_contract"
                if stage_rows
                else "missing_from_tushare_acceptance_static_contract",
                "observed_source": "scripts/tushare_acceptance_contract._tushare_production_stage_scope_rows local static contract",
                "cache_status": "tushare_acceptance_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "provider_backed_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "full_interface_acceptance_done": False,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "full_interface_selection_done": False,
                "failure_mode_evidence_done": False,
                "request_parameter_provider_window_done": False,
                "parquet_promotion_done": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_tushare_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-02",
                "goal": "Tushare 全接口生产流水线",
                "stage_scope_manifest": "tushare_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/tushare_acceptance_contract._tushare_production_stage_scope_rows local static contract",
                "error_message_safe": "tushare_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "provider_backed_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "full_interface_acceptance_done": False,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "full_interface_selection_done": False,
                "failure_mode_evidence_done": False,
                "request_parameter_provider_window_done": False,
                "parquet_promotion_done": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import factor_test_lab_contract

        stage_rows = factor_test_lab_contract._factor_test_production_stage_scope_rows()
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_factor_test_validation_complete") is False
        )
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-03",
                "goal": "Factor Test Lab 完整生产化",
                "stage_scope_manifest": "factor_test_production_stage_scope_manifest",
                "status": "observed_in_factor_test_lab_static_contract"
                if stage_rows
                else "missing_from_factor_test_lab_static_contract",
                "observed_source": "scripts/factor_test_lab_contract._factor_test_production_stage_scope_rows local static contract",
                "cache_status": "factor_test_lab_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "provider_backed_small_pool_validation_done": False,
                "full_market_validation_done": False,
                "production_factor_test_validation_complete": False,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "multi_horizon_forward_returns_done": False,
                "rolling_window_validation_done": False,
                "cost_assumption_validation_done": False,
                "neutralization_stability_done": False,
                "pit_bias_controls_done": False,
                "full_market_promotion_done": False,
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
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_factor_test_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-03",
                "goal": "Factor Test Lab 完整生产化",
                "stage_scope_manifest": "factor_test_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/factor_test_lab_contract._factor_test_production_stage_scope_rows local static contract",
                "error_message_safe": "factor_test_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "provider_backed_small_pool_validation_done": False,
                "full_market_validation_done": False,
                "production_factor_test_validation_complete": False,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "multi_horizon_forward_returns_done": False,
                "rolling_window_validation_done": False,
                "cost_assumption_validation_done": False,
                "neutralization_stability_done": False,
                "pit_bias_controls_done": False,
                "full_market_promotion_done": False,
                "metrics_remain_research_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import factor_universe_contract
        from server.services import factor_service

        required_stages = list(factor_service.FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)
        stage_rows = factor_universe_contract._worker_stage_scope_rows(required_stages, required_stages)
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("worker_execution_implemented") is False
        )
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("selected_by_worker_dry_run_scope") is True
        )
        rows.append(
            {
                "id": "LTG-04",
                "goal": "Factor 全市场 / 股票池研究",
                "stage_scope_manifest": "factor_universe_worker_batch_stage_scope_manifest",
                "status": "observed_in_factor_universe_static_contract"
                if stage_rows
                else "missing_from_factor_universe_static_contract",
                "observed_source": "scripts/factor_universe_contract._worker_stage_scope_rows local static contract",
                "cache_status": "factor_universe_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "worker_execution_implemented": False,
                "worker_batch_executed": False,
                "large_universe_pipeline_done": False,
                "cross_sectional_rank_zscore_done": False,
                "neutralization_done": False,
                "factor_combination_research_done": False,
                "full_pool_validation_done": False,
                "production_factor_universe_complete": False,
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
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_factor_universe_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-04",
                "goal": "Factor 全市场 / 股票池研究",
                "stage_scope_manifest": "factor_universe_worker_batch_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/factor_universe_contract._worker_stage_scope_rows local static contract",
                "error_message_safe": "factor_universe_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "worker_execution_implemented": False,
                "worker_batch_executed": False,
                "large_universe_pipeline_done": False,
                "cross_sectional_rank_zscore_done": False,
                "neutralization_done": False,
                "factor_combination_research_done": False,
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
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import storage_contract

        stage_rows = storage_contract._physical_migration_stage_scope_rows()
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_storage_complete") is False
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("current_status") == "local_preflight_or_dry_run_only"
        )
        rows.append(
            {
                "id": "LTG-05",
                "goal": "Storage / DuckDB / Parquet 生产化",
                "stage_scope_manifest": "storage_physical_migration_stage_scope_manifest",
                "status": "observed_in_storage_static_contract"
                if stage_rows
                else "missing_from_storage_static_contract",
                "observed_source": "scripts/storage_contract._physical_migration_stage_scope_rows local static contract",
                "cache_status": "storage_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "physical_schema_validation_done": False,
                "schema_migration_executed": False,
                "dataset_version_manifest_validated": False,
                "partition_migration_executed": False,
                "physical_compaction_executed": False,
                "cache_ttl_refresh_executed": False,
                "artifact_cleanup_delete_executed": False,
                "production_storage_complete": False,
                "writes_parquet_on_get": False,
                "writes_parquet_by_contract": False,
                "reads_row_payloads": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_storage_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-05",
                "goal": "Storage / DuckDB / Parquet 生产化",
                "stage_scope_manifest": "storage_physical_migration_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/storage_contract._physical_migration_stage_scope_rows local static contract",
                "error_message_safe": "storage_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "physical_schema_validation_done": False,
                "schema_migration_executed": False,
                "dataset_version_manifest_validated": False,
                "partition_migration_executed": False,
                "physical_compaction_executed": False,
                "cache_ttl_refresh_executed": False,
                "artifact_cleanup_delete_executed": False,
                "production_storage_complete": False,
                "writes_parquet_on_get": False,
                "writes_parquet_by_contract": False,
                "reads_row_payloads": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import worker_contract

        evidence_scope = list(worker_contract.REQUIRED_RUNTIME_EVIDENCE_STAGES)
        stage_rows = worker_contract._worker_runtime_evidence_stage_scope_rows(evidence_scope)
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_worker_complete") is False
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("selected_by_evidence_plan_scope") is True
        )
        rows.append(
            {
                "id": "LTG-06",
                "goal": "Worker / Celery / Redis 生产化",
                "stage_scope_manifest": "worker_runtime_evidence_stage_scope_manifest",
                "status": "observed_in_worker_static_contract"
                if stage_rows
                else "missing_from_worker_static_contract",
                "observed_source": "scripts/worker_contract._worker_runtime_evidence_stage_scope_rows local static contract",
                "cache_status": "worker_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "worker_started": False,
                "celery_worker_started": False,
                "redis_pinged": False,
                "scheduler_started": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "healthcheck_executed": False,
                "runtime_qa_executed": False,
                "task_log_persistence_verified": False,
                "append_only_worker_log_verified": False,
                "cross_process_task_control_verified": False,
                "activation_ready": False,
                "production_worker_complete": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_worker_runtime_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-06",
                "goal": "Worker / Celery / Redis 生产化",
                "stage_scope_manifest": "worker_runtime_evidence_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/worker_contract._worker_runtime_evidence_stage_scope_rows local static contract",
                "error_message_safe": "worker_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "worker_started": False,
                "celery_worker_started": False,
                "redis_pinged": False,
                "scheduler_started": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "healthcheck_executed": False,
                "runtime_qa_executed": False,
                "task_log_persistence_verified": False,
                "append_only_worker_log_verified": False,
                "cross_process_task_control_verified": False,
                "activation_ready": False,
                "production_worker_complete": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import deepseek_governance_contract

        stage_rows = deepseek_governance_contract._deepseek_production_stage_scope_rows()
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("production_deepseek_explanation_complete") is False
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("current_status") == "local_governance_or_dry_run_only"
        )
        rows.append(
            {
                "id": "LTG-07",
                "goal": "DeepSeek pro 稳定解释生产化",
                "stage_scope_manifest": "deepseek_production_stage_scope_manifest",
                "status": "observed_in_deepseek_governance_static_contract"
                if stage_rows
                else "missing_from_deepseek_governance_static_contract",
                "observed_source": "scripts/deepseek_governance_contract._deepseek_production_stage_scope_rows local static contract",
                "cache_status": "deepseek_governance_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "provider_benchmark_done": False,
                "response_format_enforced": False,
                "bounded_retry_repair_executed": False,
                "token_budget_cost_evidence_complete": False,
                "auto_after_task_production_ready": False,
                "model_execution_implemented": False,
                "production_deepseek_explanation_complete": False,
                "deepseek_called_by_contract": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_deepseek_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-07",
                "goal": "DeepSeek pro 稳定解释生产化",
                "stage_scope_manifest": "deepseek_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/deepseek_governance_contract._deepseek_production_stage_scope_rows local static contract",
                "error_message_safe": "deepseek_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
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
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from server.services import candidate_service

        candidate_packet = candidate_service.read_candidate_radar_cache()
        if not isinstance(candidate_packet, dict):
            candidate_packet = {}
        manifest = candidate_packet.get("candidate_radar_production_stage_scope_manifest")
        manifest = manifest if isinstance(manifest, dict) else {}
        stage_rows = candidate_packet.get("candidate_radar_production_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        counts = candidate_packet.get("counts")
        counts = counts if isinstance(counts, dict) else {}
        promotion_dry_run = candidate_packet.get("candidate_radar_production_promotion_dry_run_receipt")
        promotion_dry_run = promotion_dry_run if isinstance(promotion_dry_run, dict) else {}
        manifest_visible = bool(manifest)
        row_count = int(manifest.get("row_count") or len(stage_rows) or 0)
        pending_count = int(
            manifest.get("pending_stage_count")
            or counts.get("candidate_radar_production_stage_scope_pending_count")
            or 0
        )
        local_evidence_count = int(
            manifest.get("local_evidence_stage_count")
            or counts.get("candidate_radar_production_stage_scope_local_evidence_count")
            or 0
        )
        rows.append(
            {
                "id": "LTG-13",
                "goal": "下一票雷达快扫生产化",
                "stage_scope_manifest": "candidate_radar_production_stage_scope_manifest",
                "status": "observed_in_candidate_radar_cache" if manifest_visible else "missing_from_candidate_radar_cache",
                "observed_source": "GET /api/candidate-radar/cache local builder",
                "cache_status": str(candidate_packet.get("status") or "missing"),
                "cache_mode": str(candidate_packet.get("mode") or "cache_only"),
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": int(manifest.get("production_blocker_count") or pending_count),
                "production_radar_replacement_complete": manifest.get("production_radar_replacement_complete") is True,
                "legacy_retirement_ready": manifest.get("legacy_retirement_ready") is True,
                "full_pool_scan_done": manifest.get("full_pool_scan_done") is True,
                "deep_scan_done": manifest.get("deep_scan_done") is True,
                "provider_backed_acceptance_done": manifest.get("provider_backed_acceptance_done") is True,
                "worker_backed_execution_done": manifest.get("worker_backed_execution_done") is True,
                "browser_visual_delta_qa_done": manifest.get("browser_visual_delta_qa_done") is True,
                "durable_ci_evidence_complete": manifest.get("durable_ci_evidence_complete") is True,
                "production_promotion_dry_run_visible": bool(promotion_dry_run),
                "production_promotion_dry_run_status": str(promotion_dry_run.get("status") or "missing"),
                "production_promotion_dry_run_route": str(
                    promotion_dry_run.get("route") or "POST /api/candidate-radar/production-promotion-dry-run"
                ),
                "production_promotion_dry_run_explicit_task_done": (
                    promotion_dry_run.get("explicit_promotion_dry_run_task_done") is True
                ),
                "production_promotion_dry_run_ready_for_local_review": (
                    promotion_dry_run.get("ready_for_local_promotion_review") is True
                ),
                "production_promotion_dry_run_production_blocker_count": int(
                    promotion_dry_run.get("production_blocker_count")
                    or counts.get("candidate_radar_production_promotion_dry_run_production_blocker_count")
                    or 0
                ),
                "production_promotion_dry_run_can_close_goal": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_cache_stage_scope_manifest_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-13",
                "goal": "下一票雷达快扫生产化",
                "stage_scope_manifest": "candidate_radar_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "GET /api/candidate-radar/cache local builder",
                "error_message_safe": "candidate_radar_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "production_radar_replacement_complete": False,
                "legacy_retirement_ready": False,
                "production_promotion_dry_run_visible": False,
                "production_promotion_dry_run_status": "observation_failed",
                "production_promotion_dry_run_route": "POST /api/candidate-radar/production-promotion-dry-run",
                "production_promotion_dry_run_explicit_task_done": False,
                "production_promotion_dry_run_ready_for_local_review": False,
                "production_promotion_dry_run_production_blocker_count": 0,
                "production_promotion_dry_run_can_close_goal": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import next_session_map_contract

        next_session_contract = next_session_map_contract.build_contract()
        if not isinstance(next_session_contract, dict):
            next_session_contract = {}
        observed = next_session_contract.get("observed")
        observed = observed if isinstance(observed, dict) else {}
        stage_rows = next_session_contract.get("production_replacement_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = int(observed.get("production_stage_scope_count") or len(stage_rows) or 0)
        pending_count = int(
            observed.get("production_stage_scope_pending_count")
            or sum(
                1
                for row in stage_rows
                if isinstance(row, dict) and row.get("production_replacement_complete") is False
            )
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict)
            and (row.get("exact_payload_contract_ready") is True or row.get("interaction_contract_ready") is True)
        )
        rows.append(
            {
                "id": "LTG-08",
                "goal": "ECharts 次日操作图谱成熟版",
                "stage_scope_manifest": "next_session_production_replacement_stage_scope_manifest",
                "status": "observed_in_next_session_map_static_contract"
                if stage_rows
                else "missing_from_next_session_map_static_contract",
                "observed_source": "scripts/next_session_map_contract.build_contract local static contract",
                "cache_status": str(next_session_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "production_replacement_complete": next_session_contract.get("production_replacement_complete") is True,
                "streamlit_parity_complete": next_session_contract.get("streamlit_parity_complete") is True,
                "browser_visual_qa_done": next_session_contract.get("browser_visual_qa_done") is True,
                "browser_performance_trace_done": next_session_contract.get("browser_performance_trace_done") is True,
                "durable_ci_evidence_complete": next_session_contract.get("durable_evidence_complete") is True,
                "frontend_computes_trade_action": next_session_contract.get("frontend_computes_trade_action") is True,
                "does_not_modify_operation_zones": next_session_contract.get("does_not_modify_operation_zones") is True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_next_session_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-08",
                "goal": "ECharts 次日操作图谱成熟版",
                "stage_scope_manifest": "next_session_production_replacement_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/next_session_map_contract.build_contract local static contract",
                "error_message_safe": "next_session_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "production_replacement_complete": False,
                "streamlit_parity_complete": False,
                "browser_visual_qa_done": False,
                "browser_performance_trace_done": False,
                "durable_ci_evidence_complete": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import tauri_desktop_contract

        tauri_contract = tauri_desktop_contract.build_contract()
        if not isinstance(tauri_contract, dict):
            tauri_contract = {}
        observed = tauri_contract.get("observed")
        observed = observed if isinstance(observed, dict) else {}
        stage_rows = tauri_contract.get("production_package_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = int(observed.get("production_package_stage_scope_count") or len(stage_rows) or 0)
        pending_count = int(
            observed.get("production_package_stage_scope_pending_count")
            or sum(
                1
                for row in stage_rows
                if isinstance(row, dict) and row.get("production_package_complete") is False
            )
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("current_status") == "local_manifest_or_static_qa_only"
        )
        rows.append(
            {
                "id": "LTG-09",
                "goal": "Tauri desktop production package",
                "stage_scope_manifest": "tauri_production_package_stage_scope_manifest",
                "status": "observed_in_tauri_desktop_static_contract"
                if stage_rows
                else "missing_from_tauri_desktop_static_contract",
                "observed_source": "scripts/tauri_desktop_contract.build_contract local static contract",
                "cache_status": str(tauri_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "production_package_complete": tauri_contract.get("production_package_complete") is True,
                "tauri_build_executed": tauri_contract.get("tauri_build_executed") is True,
                "packaged_runtime_qa_done": tauri_contract.get("packaged_runtime_qa_done") is True,
                "tauri_package_durable_evidence_complete": tauri_contract.get(
                    "tauri_package_durable_evidence_complete"
                )
                is True,
                "tauri_runtime_started_by_contract": False,
                "packaged_app_opened_by_contract": False,
                "fastapi_started_by_contract": False,
                "config_values_read_by_contract": False,
                "log_files_written_by_contract": False,
                "provider_model_task_dispatched_by_contract": False,
                "release_binary_detected": any(
                    isinstance(row, dict) and row.get("release_binary_detected") is True for row in stage_rows
                ),
                "release_binary_is_completion": False,
                "app_bundle_detected": False,
                "dmg_distribution_detected": False,
                "backend_startup_runtime_validated": False,
                "backend_offline_packaged_ux_verified": False,
                "config_log_runtime_paths_validated": False,
                "signing_notarization_done": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_tauri_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-09",
                "goal": "Tauri desktop production package",
                "stage_scope_manifest": "tauri_production_package_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/tauri_desktop_contract.build_contract local static contract",
                "error_message_safe": "tauri_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "production_package_complete": False,
                "tauri_build_executed": False,
                "packaged_runtime_qa_done": False,
                "tauri_package_durable_evidence_complete": False,
                "tauri_runtime_started_by_contract": False,
                "packaged_app_opened_by_contract": False,
                "fastapi_started_by_contract": False,
                "config_values_read_by_contract": False,
                "log_files_written_by_contract": False,
                "provider_model_task_dispatched_by_contract": False,
                "release_binary_detected": False,
                "release_binary_is_completion": False,
                "app_bundle_detected": False,
                "dmg_distribution_detected": False,
                "backend_startup_runtime_validated": False,
                "backend_offline_packaged_ux_verified": False,
                "config_log_runtime_paths_validated": False,
                "signing_notarization_done": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import streamlit_legacy_contract

        streamlit_contract = streamlit_legacy_contract.build_contract()
        if not isinstance(streamlit_contract, dict):
            streamlit_contract = {}
        observed = streamlit_contract.get("observed")
        observed = observed if isinstance(observed, dict) else {}
        stage_rows = streamlit_contract.get("streamlit_retirement_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = int(observed.get("streamlit_retirement_stage_scope_count") or len(stage_rows) or 0)
        pending_count = int(
            observed.get("streamlit_retirement_stage_scope_pending_count")
            or sum(
                1
                for row in stage_rows
                if isinstance(row, dict) and row.get("full_streamlit_removal_ready") is False
            )
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("current_status") == "local_exit_audit_or_dependency_contract_only"
        )
        rows.append(
            {
                "id": "LTG-10",
                "goal": "Streamlit 完全退出普通主流程",
                "stage_scope_manifest": "streamlit_retirement_stage_scope_manifest",
                "status": "observed_in_streamlit_legacy_static_contract"
                if stage_rows
                else "missing_from_streamlit_legacy_static_contract",
                "observed_source": "scripts/streamlit_legacy_contract.build_contract local static contract",
                "cache_status": str(streamlit_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "ordinary_workflow_exit_complete": streamlit_contract.get("ordinary_workflow_exit_complete")
                is True,
                "streamlit_fallback_removal_ready": streamlit_contract.get("streamlit_fallback_removal_ready")
                is True,
                "full_streamlit_removal_ready": streamlit_contract.get("full_streamlit_removal_ready") is True,
                "streamlit_fallback_retained": streamlit_contract.get("streamlit_fallback_retained") is True,
                "legacy_fallback_required": streamlit_contract.get("legacy_fallback_required") is True,
                "feature_parity_required_before_removal": streamlit_contract.get(
                    "feature_parity_required_before_removal"
                )
                is True,
                "no_feature_cut_allowed": streamlit_contract.get("no_feature_cut_allowed") is True,
                "streamlit_retirement_durable_evidence_complete": streamlit_contract.get(
                    "streamlit_retirement_durable_evidence_complete"
                )
                is True,
                "replacement_parity_complete": False,
                "candidate_radar_parity_complete": False,
                "provider_backed_parity_done": False,
                "browser_performance_qa_done": False,
                "admin_debug_retention_decision_done": False,
                "fallback_removed_by_contract": False,
                "app_py_deleted_by_contract": False,
                "streamlit_opened_by_contract": False,
                "legacy_tools_run_by_contract": False,
                "tasks_created_by_contract": False,
                "provider_model_task_dispatched_by_contract": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_streamlit_stage_scope_not_retirement_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-10",
                "goal": "Streamlit 完全退出普通主流程",
                "stage_scope_manifest": "streamlit_retirement_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/streamlit_legacy_contract.build_contract local static contract",
                "error_message_safe": "streamlit_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "ordinary_workflow_exit_complete": False,
                "streamlit_fallback_removal_ready": False,
                "full_streamlit_removal_ready": False,
                "streamlit_fallback_retained": True,
                "legacy_fallback_required": True,
                "feature_parity_required_before_removal": True,
                "no_feature_cut_allowed": True,
                "streamlit_retirement_durable_evidence_complete": False,
                "replacement_parity_complete": False,
                "candidate_radar_parity_complete": False,
                "provider_backed_parity_done": False,
                "browser_performance_qa_done": False,
                "admin_debug_retention_decision_done": False,
                "fallback_removed_by_contract": False,
                "app_py_deleted_by_contract": False,
                "streamlit_opened_by_contract": False,
                "legacy_tools_run_by_contract": False,
                "tasks_created_by_contract": False,
                "provider_model_task_dispatched_by_contract": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from server.services import audit_service

        release_gate, _, workflow_rows = audit_service._release_gate_readiness_audit()
        release_gate = release_gate if isinstance(release_gate, dict) else {}
        ci_triage_contract, _ = audit_service._ci_notification_triage_contract(release_gate, workflow_rows)
        ci_triage_contract = ci_triage_contract if isinstance(ci_triage_contract, dict) else {}
        push_receipt, _ = audit_service._release_gate_push_readiness_receipt(release_gate, ci_triage_contract)
        push_receipt = push_receipt if isinstance(push_receipt, dict) else {}
        stage_rows = audit_service._release_gate_stage_scope_rows(
            release_gate,
            push_receipt,
            ci_triage_contract,
        )
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = len(stage_rows)
        pending_count = int(
            sum(1 for row in stage_rows if isinstance(row, dict) and row.get("stage_complete") is False)
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict)
            and row.get("local_static_contract_ready") is True
            and row.get("ci_mirror_ready") is True
        )
        rows.append(
            {
                "id": "LTG-11",
                "goal": "测试 / CI / smoke / 安全扫描标准化",
                "stage_scope_manifest": "release_gate_stage_scope_manifest",
                "status": "observed_in_audit_cache_release_gate_contract"
                if stage_rows
                else "missing_from_audit_cache_release_gate_contract",
                "observed_source": "server.services.audit_service release gate local static helpers also surfaced by GET /api/audit/cache",
                "cache_status": "ready" if stage_rows else "missing",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "local_gate_ready": release_gate.get("local_gate_ready") is True,
                "ci_mirror_ready": release_gate.get("ci_mirror_ready") is True,
                "push_readiness_receipt_ready": push_receipt.get("local_receipt_ready") is True,
                "ready_for_explicit_push_sequence": push_receipt.get("ready_for_explicit_local_gate_then_push")
                is True,
                "release_gate_complete": release_gate.get("release_gate_complete") is True,
                "fresh_local_gate_run_observed": False,
                "remote_actions_status_known": False,
                "latest_remote_run_verified_green": False,
                "failure_email_has_matching_head_and_logs": False,
                "can_dismiss_failure_email_without_matching_head_and_logs": False,
                "periodic_allowlist_review_ready": False,
                "release_report_written_by_cache": False,
                "release_report_is_ci_status": False,
                "did_not_push": True,
                "git_add_dot_used": False,
                "github_api_called": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_release_gate_stage_scope_not_fresh_gate_or_remote_ci_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-11",
                "goal": "测试 / CI / smoke / 安全扫描标准化",
                "stage_scope_manifest": "release_gate_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "server.services.audit_service release gate local static helpers also surfaced by GET /api/audit/cache",
                "error_message_safe": "release_gate_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "local_gate_ready": False,
                "ci_mirror_ready": False,
                "push_readiness_receipt_ready": False,
                "ready_for_explicit_push_sequence": False,
                "release_gate_complete": False,
                "fresh_local_gate_run_observed": False,
                "remote_actions_status_known": False,
                "latest_remote_run_verified_green": False,
                "failure_email_has_matching_head_and_logs": False,
                "can_dismiss_failure_email_without_matching_head_and_logs": False,
                "periodic_allowlist_review_ready": False,
                "release_report_written_by_cache": False,
                "release_report_is_ci_status": False,
                "did_not_push": True,
                "git_add_dot_used": False,
                "github_api_called": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import trade_isolation_contract

        isolation_contract = trade_isolation_contract.build_contract()
        if not isinstance(isolation_contract, dict):
            isolation_contract = {}
        observed = isolation_contract.get("observed")
        observed = observed if isinstance(observed, dict) else {}
        stage_rows = isolation_contract.get("trade_isolation_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = int(observed.get("trade_isolation_stage_scope_count") or len(stage_rows) or 0)
        pending_count = int(
            observed.get("trade_isolation_stage_scope_pending_count")
            or sum(
                1
                for row in stage_rows
                if isinstance(row, dict)
                and row.get("target_status") == "separate_real_trading_project_evidence_required"
            )
        )
        local_evidence_count = sum(
            1
            for row in stage_rows
            if isinstance(row, dict) and row.get("current_status") == "current_research_client_isolated"
        )
        rows.append(
            {
                "id": "LTG-12",
                "goal": "真实交易链路继续保持隔离",
                "stage_scope_manifest": "trade_isolation_stage_scope_manifest",
                "status": "observed_in_trade_isolation_static_contract"
                if stage_rows
                else "missing_from_trade_isolation_static_contract",
                "observed_source": "scripts/trade_isolation_contract.build_contract local static contract",
                "cache_status": str(isolation_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "trade_isolation_release_receipt_ready": isolation_contract.get(
                    "trade_isolation_release_receipt_ready"
                )
                is True,
                "trade_isolation_release_receipt_status": isolation_contract.get(
                    "trade_isolation_release_receipt_status"
                ),
                "ready_for_real_trading_integration": False,
                "real_trading_connected": False,
                "broker_adapter_connected": isolation_contract.get("broker_adapter_connected") is True,
                "order_endpoint_present": isolation_contract.get("order_endpoint_present") is True,
                "trade_execution_api_enabled": False,
                "order_route_present": False,
                "frontend_trade_controls_present": False,
                "model_or_provider_can_modify_action": False,
                "strategy_action_mutated_by_contract": False,
                "paper_trading_sandbox_ready": False,
                "separate_project_approved": False,
                "future_real_trading_requires_separate_project": True,
                "release_receipt_is_trading_approval": False,
                "broker_called": False,
                "order_submitted": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_trade_isolation_not_real_trading_integration",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-12",
                "goal": "真实交易链路继续保持隔离",
                "stage_scope_manifest": "trade_isolation_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/trade_isolation_contract.build_contract local static contract",
                "error_message_safe": "trade_isolation_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "trade_isolation_release_receipt_ready": False,
                "trade_isolation_release_receipt_status": "",
                "ready_for_real_trading_integration": False,
                "real_trading_connected": False,
                "broker_adapter_connected": False,
                "order_endpoint_present": False,
                "trade_execution_api_enabled": False,
                "order_route_present": False,
                "frontend_trade_controls_present": False,
                "model_or_provider_can_modify_action": False,
                "strategy_action_mutated_by_contract": False,
                "paper_trading_sandbox_ready": False,
                "separate_project_approved": False,
                "future_real_trading_requires_separate_project": True,
                "release_receipt_is_trading_approval": False,
                "broker_called": False,
                "order_submitted": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    try:
        from scripts import motion_viewport_qa_contract

        motion_contract = motion_viewport_qa_contract.build_contract()
        if not isinstance(motion_contract, dict):
            motion_contract = {}
        stage_rows = motion_contract.get("motion_production_stage_scope_rows")
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        row_count = int(motion_contract.get("motion_production_stage_scope_count") or len(stage_rows) or 0)
        pending_count = int(
            motion_contract.get("motion_production_stage_scope_pending_count")
            or sum(1 for row in stage_rows if isinstance(row, dict) and row.get("production_motion_complete") is False)
        )
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-14",
                "goal": "App 动效与可视化清晰度生产化",
                "stage_scope_manifest": "motion_production_stage_scope_manifest",
                "status": "observed_in_motion_viewport_static_contract"
                if stage_rows
                else "missing_from_motion_viewport_static_contract",
                "observed_source": "scripts/motion_viewport_qa_contract.build_contract local static contract",
                "cache_status": str(motion_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "production_blocker_count": pending_count,
                "production_motion_complete": motion_contract.get("production_motion_complete") is True,
                "visual_qa_complete": motion_contract.get("visual_qa_complete") is True,
                "browser_performance_verified": motion_contract.get("browser_performance_verified") is True,
                "browser_visual_qa_promoted": False,
                "browser_performance_promoted": False,
                "durable_ci_evidence_complete": False,
                "browser_runner_executed_by_contract": False,
                "local_artifact_reviewed_for_production": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_local_static_motion_stage_scope_not_production_completion",
            }
        )
    except Exception:
        rows.append(
            {
                "id": "LTG-14",
                "goal": "App 动效与可视化清晰度生产化",
                "stage_scope_manifest": "motion_production_stage_scope_manifest",
                "status": "local_observation_failed_safe_fallback",
                "observed_source": "scripts/motion_viewport_qa_contract.build_contract local static contract",
                "error_message_safe": "motion_stage_scope_observation_failed",
                "row_count": 0,
                "pending_stage_count": 0,
                "local_evidence_stage_count": 0,
                "production_blocker_count": 0,
                "production_motion_complete": False,
                "visual_qa_complete": False,
                "browser_performance_verified": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observation_failure_is_not_completion",
            }
        )
    return rows


def _merge_ltg_stage_scope_observations(
    rows: list[dict[str, Any]],
    observed_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observed_by_id = {str(row.get("id") or ""): row for row in observed_rows}
    merged: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        observed = observed_by_id.get(str(item.get("id") or ""))
        if observed:
            item["observed_stage_scope_manifest_status"] = observed.get("status")
            item["observed_stage_scope_manifest_source"] = observed.get("observed_source")
            item["observed_stage_scope_row_count"] = observed.get("row_count")
            item["observed_stage_scope_pending_count"] = observed.get("pending_stage_count")
            item["observed_stage_scope_local_evidence_count"] = observed.get("local_evidence_stage_count")
            item["observed_stage_scope_can_close_goal"] = False
            if str(item.get("id") or "") == "LTG-13":
                item["observed_production_promotion_dry_run_status"] = observed.get(
                    "production_promotion_dry_run_status"
                )
                item["observed_production_promotion_dry_run_visible"] = observed.get(
                    "production_promotion_dry_run_visible"
                )
                item["observed_production_promotion_dry_run_ready_for_local_review"] = observed.get(
                    "production_promotion_dry_run_ready_for_local_review"
                )
                item["observed_production_promotion_dry_run_production_blocker_count"] = observed.get(
                    "production_promotion_dry_run_production_blocker_count"
                )
                item["observed_production_promotion_dry_run_can_close_goal"] = False
        merged.append(item)
    return merged


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


def _linkage_review_task_row(
    phase: str,
    *,
    status: str,
    evidence: str,
    required_evidence: list[str],
    passed: bool,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "required_evidence": required_evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _build_tushare_deepseek_linkage_review_task_receipt(
    *,
    linkage_review: dict[str, Any],
    linkage_rows: list[dict[str, Any]],
    mode_layer_rows: list[dict[str, Any]],
    payload_safe: dict[str, Any],
    task_id: str,
    reviewed_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    linkage_by_key = {str(row.get("linkage_key") or ""): row for row in linkage_rows}
    mode_by_key = {str(row.get("layer_key") or ""): row for row in mode_layer_rows}
    user_confirmed = payload_safe.get("approved_by_user") is True or payload_safe.get("user_confirmed") is True
    provider_row = linkage_by_key.get("tushare_light_provider_execution", {})
    model_row = linkage_by_key.get("deepseek_pro_after_task_execution", {})
    promotion_row = linkage_by_key.get("production_promotion_boundary", {})
    real_trade_row = linkage_by_key.get("real_trading_boundary", {})
    cache_render_silent = (
        linkage_review.get("cache_render_silent") is True
        and linkage_review.get("cache_get_calls_tushare") is False
        and linkage_review.get("cache_get_calls_deepseek") is False
        and linkage_review.get("react_render_calls_tushare") is False
        and linkage_review.get("react_render_calls_deepseek") is False
    )
    post_task_gate_visible = (
        linkage_review.get("post_task_creation_button_gated") is True
        and mode_by_key.get("post_task_creation", {}).get("current_status") == "button_gated_allowed"
    )
    provider_evidence_done = provider_row.get("provider_execution_implemented") is True
    model_evidence_done = model_row.get("model_execution_implemented") is True
    production_promotion_done = promotion_row.get("production_promotion_complete") is True
    real_trading_isolated = real_trade_row.get("real_trading_connected") is False
    rows = [
        _linkage_review_task_row(
            "explicit_user_confirmation",
            status="passed_user_confirmed" if user_confirmed else "blocked_user_confirmation_required",
            evidence="operator confirmed local linkage review" if user_confirmed else "missing approved_by_user/user_confirmed flag",
            required_evidence=["explicit reviewer confirmation before recording a review receipt"],
            passed=user_confirmed,
            production_blocker=not user_confirmed,
        ),
        _linkage_review_task_row(
            "cache_render_silence",
            status="passed_cache_render_silent" if cache_render_silent else "blocked_cache_render_boundary_regression",
            evidence="GET cache and initial React render remain provider/model silent.",
            required_evidence=["cache_get_no_tushare", "cache_get_no_deepseek", "react_render_no_provider_model_call"],
            passed=cache_render_silent,
            production_blocker=not cache_render_silent,
        ),
        _linkage_review_task_row(
            "post_task_gate_visible",
            status="passed_button_task_gate_visible" if post_task_gate_visible else "blocked_missing_post_task_gate",
            evidence="Tushare/DeepSeek work is represented as explicit task/mode-gated rows.",
            required_evidence=["visible runtime mode", "button or live_light task boundary", "safe payload", "call/model ledger requirements"],
            passed=post_task_gate_visible,
            production_blocker=not post_task_gate_visible,
        ),
        _linkage_review_task_row(
            "tushare_call_ledger_evidence",
            status="pending_real_tushare_call_ledger",
            evidence=str(provider_row.get("status") or "pending_real_call_ledger"),
            required_evidence=list(provider_row.get("required_evidence") or []),
            passed=provider_evidence_done,
            production_blocker=not provider_evidence_done,
        ),
        _linkage_review_task_row(
            "deepseek_model_ledger_evidence",
            status="pending_deepseek_model_ledger_and_benchmark",
            evidence=str(model_row.get("status") or "pending_model_ledger_and_benchmark"),
            required_evidence=list(model_row.get("required_evidence") or []),
            passed=model_evidence_done,
            production_blocker=not model_evidence_done,
        ),
        _linkage_review_task_row(
            "github_probe_exclusion",
            status="passed_github_probe_manual_only",
            evidence=str(linkage_by_key.get("github_probe_boundary", {}).get("status") or "manual_only"),
            required_evidence=["no_live_light_default_probe", "explicit_user_action"],
            passed=linkage_by_key.get("github_probe_boundary", {}).get("github_called") is not True,
            production_blocker=False,
        ),
        _linkage_review_task_row(
            "production_promotion_evidence",
            status="pending_production_promotion_review",
            evidence=str(promotion_row.get("status") or "blocked_until_provider_model_browser_and_redaction_evidence"),
            required_evidence=list(promotion_row.get("required_evidence") or []),
            passed=production_promotion_done,
            production_blocker=not production_promotion_done,
        ),
        _linkage_review_task_row(
            "real_trading_isolation",
            status="passed_real_trading_disconnected" if real_trading_isolated else "blocked_real_trading_connected",
            evidence=str(real_trade_row.get("status") or "disconnected"),
            required_evidence=list(real_trade_row.get("required_evidence") or []),
            passed=real_trading_isolated,
            production_blocker=not real_trading_isolated,
        ),
        _linkage_review_task_row(
            "secret_boundary",
            status="passed_no_secret_value_read_or_exposed",
            evidence="review payload is sanitized by task_service and only records booleans/labels.",
            required_evidence=["no token/key in payload_safe", "no env key names in receipt", "ledger redaction review before promotion"],
            passed=True,
            production_blocker=False,
        ),
    ]
    production_blockers = [row for row in rows if row.get("production_blocker")]
    missing_evidence = sorted(
        {
            str(item)
            for row in production_blockers
            for item in row.get("required_evidence", [])
            if item
        }
    )
    if not user_confirmed:
        status = "tushare_deepseek_linkage_review_blocked_user_confirmation_required"
        allowed_next_step = "rerun_linkage_review_with_explicit_user_confirmation"
    elif production_blockers:
        status = "tushare_deepseek_linkage_review_recorded_real_evidence_pending"
        allowed_next_step = "collect_real_tushare_call_ledger_deepseek_model_ledger_browser_redaction_evidence_then_rerun_review"
    else:
        status = "tushare_deepseek_linkage_review_ready_for_manual_promotion_review"
        allowed_next_step = "run_full_push_gate_and_manual_release_review_before_any_production_promotion"
    receipt = {
        "schema_version": "command_center_3_tushare_deepseek_linkage_review_task.v1",
        "status": status,
        "scope": "local_tushare_deepseek_linkage_review_no_provider_or_model_execution",
        "route": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_ROUTE,
        "task_type": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE,
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "user_confirmed": user_confirmed,
        "mode_layer_model": linkage_review.get("mode_layer_model"),
        "boundary_interpretation": linkage_review.get("boundary_interpretation"),
        "row_count": len(rows),
        "blocking_row_count": len(production_blockers),
        "missing_evidence_items": missing_evidence,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "call Tushare from GET cache or React render",
            "call DeepSeek from GET cache or React render",
            "create GitHub probe from live_light default chain",
            "treat dry-run or local receipt as real provider/model acceptance",
            "promote production from scaffold/preflight/matrix/sanitizer/local receipt",
            "overwrite numeric fields, prices, holdings, operation_zones, or strategy action",
            "connect real trading",
        ],
        "cache_render_silent": cache_render_silent,
        "post_task_creation_button_gated": post_task_gate_visible,
        "provider_model_execution_pending": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "production_quant_projection_complete": False,
        "production_promotion_complete": False,
        "ready_for_production_promotion_review": False,
        "real_trading_disconnected": real_trading_isolated,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return receipt, rows


def _latest_tushare_deepseek_linkage_review_from_tasks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    latest_task = next(
        (
            task
            for task in task_service.list_task_statuses()
            if str(task.get("task_type") or "") == TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE
        ),
        None,
    )
    if not latest_task:
        return (
            {
                "schema_version": "command_center_3_latest_tushare_deepseek_linkage_review.v1",
                "status": "no_tushare_deepseek_linkage_review_task_found",
                "scope": "local_task_status_lookup_no_provider_or_model_execution",
                "latest_task_found": False,
                "route": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_ROUTE,
                "task_type": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE,
                "receipt_visible": False,
                "row_count": 0,
                "blocking_row_count": 0,
                "ready_for_production_promotion_review": False,
                "provider_execution_implemented": False,
                "model_execution_implemented": False,
                "production_live_light_complete": False,
                "production_quant_projection_complete": False,
                "cache_get_creates_task": False,
                "cache_get_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            [],
        )
    payload_safe = latest_task.get("payload_safe") if isinstance(latest_task.get("payload_safe"), dict) else {}
    receipt = payload_safe.get("tushare_deepseek_linkage_review_receipt")
    rows = payload_safe.get("tushare_deepseek_linkage_review_rows")
    receipt_map = receipt if isinstance(receipt, dict) else {}
    row_list = rows if isinstance(rows, list) else []
    latest = {
        "schema_version": "command_center_3_latest_tushare_deepseek_linkage_review.v1",
        "status": "latest_tushare_deepseek_linkage_review_visible",
        "scope": "local_task_status_lookup_no_provider_or_model_execution",
        "latest_task_found": True,
        "receipt_visible": bool(receipt_map),
        "route": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_ROUTE,
        "task_type": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE,
        "latest_task_id": latest_task.get("task_id"),
        "latest_task_status": latest_task.get("status"),
        "latest_task_current_step": latest_task.get("current_step"),
        "review_status": receipt_map.get("status") or "missing_receipt",
        "row_count": len(row_list),
        "blocking_row_count": sum(1 for row in row_list if isinstance(row, dict) and row.get("production_blocker")),
        "user_confirmed": receipt_map.get("user_confirmed") is True,
        "cache_render_silent": receipt_map.get("cache_render_silent") is True,
        "post_task_creation_button_gated": receipt_map.get("post_task_creation_button_gated") is True,
        "provider_model_execution_pending": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "production_quant_projection_complete": False,
        "production_promotion_complete": False,
        "ready_for_production_promotion_review": False,
        "cache_get_creates_task": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return latest, row_list


def run_tushare_deepseek_linkage_review(payload: Any = None) -> dict[str, Any]:
    payload_preview = task_service.build_task_record(
        TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE,
        payload=payload,
    )
    payload_safe = payload_preview.get("payload_safe") if isinstance(payload_preview.get("payload_safe"), dict) else {}
    linkage_rows = _build_tushare_deepseek_linkage_rows()
    mode_layer_rows = _build_tushare_deepseek_mode_layer_rows()
    linkage_review = _build_tushare_deepseek_linkage_review(linkage_rows, mode_layer_rows)
    reviewed_at = _now_iso()
    receipt, rows = _build_tushare_deepseek_linkage_review_task_receipt(
        linkage_review=linkage_review,
        linkage_rows=linkage_rows,
        mode_layer_rows=mode_layer_rows,
        payload_safe=payload_safe,
        task_id="",
        reviewed_at=reviewed_at,
    )
    payload_safe.update(
        {
            "tushare_deepseek_linkage_review_receipt": receipt,
            "tushare_deepseek_linkage_review_rows": rows,
            "linkage_review_only": True,
            "creates_provider_task": False,
            "creates_model_task": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "production_live_light_complete": False,
            "production_quant_projection_complete": False,
        }
    )
    task = task_service.create_task_record(
        TUSHARE_DEEPSEEK_LINKAGE_REVIEW_TASK_TYPE,
        output_packet_key=TUSHARE_DEEPSEEK_LINKAGE_REVIEW_PACKET_KEY,
        payload=payload_safe,
        current_step="tushare_deepseek_linkage_review_local_only",
        warnings=[
            "Tushare/DeepSeek linkage review 只保存本地审查收据，不调用 Tushare、DeepSeek 或 GitHub。",
            "linkage review 不创建 provider/model task，不把 scaffold/preflight/matrix/sanitizer/local receipt 提升为生产完成。",
            "linkage review 不执行真实交易、不修改 strategy action、不读取 token/key 值。",
        ],
    )
    receipt, rows = _build_tushare_deepseek_linkage_review_task_receipt(
        linkage_review=linkage_review,
        linkage_rows=linkage_rows,
        mode_layer_rows=mode_layer_rows,
        payload_safe=payload_safe,
        task_id=str(task.get("task_id") or ""),
        reviewed_at=reviewed_at,
    )
    task_payload = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    task_payload.update(
        {
            "tushare_deepseek_linkage_review_receipt": receipt,
            "tushare_deepseek_linkage_review_rows": rows,
        }
    )
    task["payload_safe"] = task_payload
    ledger = [
        {
            "api": "local_tushare_deepseek_linkage_review",
            "endpoint": TUSHARE_DEEPSEEK_LINKAGE_REVIEW_ROUTE,
            "request_params_safe": {
                "review_status": receipt["status"],
                "user_confirmed": receipt["user_confirmed"],
                "cache_render_silent": receipt["cache_render_silent"],
                "post_task_creation_button_gated": receipt["post_task_creation_button_gated"],
                "provider_execution_implemented": False,
                "model_execution_implemented": False,
                "blocking_row_count": receipt["blocking_row_count"],
            },
            "row_count": len(rows),
            "local_fetched_at": reviewed_at,
            "call_status": receipt["status"],
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
    status_to_step = {
        "tushare_deepseek_linkage_review_blocked_user_confirmation_required": (
            "tushare_deepseek_linkage_review_blocked_user_confirmation_required_no_external_call"
        ),
        "tushare_deepseek_linkage_review_recorded_real_evidence_pending": (
            "tushare_deepseek_linkage_review_recorded_real_evidence_pending_no_external_call"
        ),
        "tushare_deepseek_linkage_review_ready_for_manual_promotion_review": (
            "tushare_deepseek_linkage_review_ready_for_manual_promotion_review_no_external_call"
        ),
    }
    current_step = status_to_step.get(
        str(receipt.get("status") or ""),
        "tushare_deepseek_linkage_review_recorded_no_external_call",
    )
    task_service._persist_task(task)
    return task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=TUSHARE_DEEPSEEK_LINKAGE_REVIEW_PACKET_KEY,
        call_ledger=ledger,
        warning="tushare_deepseek_linkage_review_completed_no_external_call",
    ) or task


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
    ltg_stage_scope_observed_rows = _build_ltg_stage_scope_observed_rows()
    long_term_goal_rows = _merge_ltg_stage_scope_observations(
        _enrich_long_term_goal_rows([dict(item) for item in LONG_TERM_GOAL_PROGRESS]),
        ltg_stage_scope_observed_rows,
    )
    long_term_goal_summary = _build_long_term_goal_summary(long_term_goal_rows)
    ltg_acceptance_runway_rows = _build_ltg_acceptance_runway_rows(long_term_goal_rows)
    ltg_next_acceptance_action_rows = _build_ltg_next_acceptance_action_rows(long_term_goal_rows)
    tushare_deepseek_linkage_rows = _build_tushare_deepseek_linkage_rows()
    tushare_deepseek_mode_layer_rows = _build_tushare_deepseek_mode_layer_rows()
    tushare_deepseek_linkage_review = _build_tushare_deepseek_linkage_review(
        tushare_deepseek_linkage_rows,
        tushare_deepseek_mode_layer_rows,
    )
    latest_tushare_deepseek_linkage_review, latest_tushare_deepseek_linkage_review_rows = (
        _latest_tushare_deepseek_linkage_review_from_tasks()
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
        "ltg_acceptance_runway_rows": ltg_acceptance_runway_rows,
        "ltg_next_acceptance_action_rows": ltg_next_acceptance_action_rows,
        "ltg_stage_scope_observed_rows": ltg_stage_scope_observed_rows,
        "tushare_deepseek_linkage_review": tushare_deepseek_linkage_review,
        "tushare_deepseek_linkage_rows": tushare_deepseek_linkage_rows,
        "tushare_deepseek_mode_layer_rows": tushare_deepseek_mode_layer_rows,
        "latest_tushare_deepseek_linkage_review": latest_tushare_deepseek_linkage_review,
        "latest_tushare_deepseek_linkage_review_rows": latest_tushare_deepseek_linkage_review_rows,
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
                + len(ltg_stage_scope_observed_rows)
                + len(tushare_deepseek_linkage_rows)
                + len(tushare_deepseek_mode_layer_rows),
                "ltg_stage_scope_observed_row_count": len(ltg_stage_scope_observed_rows),
                "tushare_deepseek_linkage_row_count": len(tushare_deepseek_linkage_rows),
                "tushare_deepseek_mode_layer_row_count": len(tushare_deepseek_mode_layer_rows),
                "latest_tushare_deepseek_linkage_review_found": bool(
                    latest_tushare_deepseek_linkage_review.get("latest_task_found")
                ),
                "latest_tushare_deepseek_linkage_review_row_count": len(
                    latest_tushare_deepseek_linkage_review_rows
                ),
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
            "LTG stage-scope observed rows 只读取本地 cache 或静态合同里的阶段清单；它们不是生产完成证据。",
            "14 个长期目标严格关闭数仍为 0/14；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。",
            "Tushare / DeepSeek 联动按四层审查：cache/render 安静、POST task 门控、task 内真实 provider/model execution、production promotion ledger；真实执行与生产提升仍需后续显式验收。",
            "进度表用于规划判断，不代表自动完成迁移；后续阶段仍需逐项实现和测试。",
        ],
    }
