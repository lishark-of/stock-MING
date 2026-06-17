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
        "completion_estimate": "40%-50%",
        "current_state": "local quick-scan readiness, fast-scan task pipeline contract, no-feature-loss QA, legacy parity receipt, full/deep plan receipts, search-to-quant projection receipt, provider parity dry-run ticket, worker execution recipe, scope-bound worker execution-request ticket, scope-bound searched-symbol provider/model execution-request ticket, durable evidence recipe, production stage-scope manifest cache/React visibility, production promotion dry-run, legacy-retirement local review receipt, production-promotion local review receipt, and result-delta clarity exist.",
        "not_complete_because": "async worker execution, real provider-backed radar parity execution, full-pool/deep-scan execution, real searched-symbol provider/model projection execution, DeepSeek model-ledger evidence when enabled, browser performance promotion, production legacy-retirement approval, and durable production replacement evidence are still pending.",
        "next_step": "Use the worker execution-request, quant projection execution-request, durable evidence recipe, promotion dry-run, legacy-retirement local review, and production-promotion local review to bind real worker full-pool/deep-scan evidence, provider parity call ledger, real Tushare light call ledger, optional DeepSeek model ledger, browser performance/visual proof, and release evidence before any production replacement or legacy retirement claim.",
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
    "P0 LTG-11 push gate / local status honesty",
    "P1 LTG-01 trade_cal freshness provider acceptance",
    "P2 LTG-02 Tushare staged provider samples",
    "P3 LTG-03/LTG-04/LTG-13 small-pool factor, universe research, and radar validation",
    "P4 LTG-05/LTG-06 storage and worker productionization",
    "P5 LTG-07/LTG-08 DeepSeek and ECharts promotion",
    "P6 LTG-09 Tauri package",
    "P7 LTG-10 Streamlit retirement",
    "P8 LTG-14 motion clarity promotion",
    "P10 LTG-12 real-trading isolation invariant",
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
        "queue_id": "p3_factor_universe_worker_batch_research",
        "priority": "P3",
        "ltg_ids": ["LTG-04"],
        "action_label": "Bind Factor universe worker-batch research scope evidence",
        "mode_layer": "button_task_then_future_worker_execution",
        "current_phase": "worker_batch_scope_ticket_execution_request_and_local_research_receipt_required",
        "first_allowed_route": "POST /api/factor-quant/universe-worker-batch-dry-run",
        "second_allowed_route": "POST /api/factor-quant/universe-worker-batch-execution-request",
        "future_provider_route": "future worker runtime storage metric and promotion evidence",
        "target_acceptance_mode": "worker_backed_factor_universe_research_pipeline",
        "required_evidence": [
            "approved universe worker-batch scope ticket",
            "execution recipe bound to scope hash",
            "manual execution-request ticket",
            "future worker-backed rank/zscore evidence",
            "future neutralization and batching evidence",
            "durable no-UI-blocking research evidence",
        ],
        "not_allowed_next_steps": [
            "run full-pool computation from React render",
            "start worker from GET cache",
            "treat dry-run scope as full-universe research",
            "let research output modify strategy action",
        ],
    },
    {
        "queue_id": "p3_candidate_radar_provider_worker_promotion",
        "priority": "P3",
        "ltg_ids": ["LTG-13"],
        "action_label": "Bind Candidate Radar provider/model/worker promotion evidence",
        "mode_layer": "button_task_then_worker_or_provider_execution",
        "current_phase": "promotion_review_ticket_and_direct_evidence_required",
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
            "local production promotion review before real execution handoff",
        ],
        "not_allowed_next_steps": [
            "run full-pool/deep-scan from render",
            "hide provider or freshness gaps",
            "generate buy/sell candidates from local-only evidence",
            "retire legacy radar before parity evidence",
        ],
    },
    {
        "queue_id": "p4_storage_physical_execution",
        "priority": "P4",
        "ltg_ids": ["LTG-05"],
        "action_label": "Bind Storage physical execution request evidence",
        "mode_layer": "button_task_then_physical_storage_execution",
        "current_phase": "physical_execution_request_required",
        "first_allowed_route": "POST /api/storage/physical-execution-request",
        "second_allowed_route": "",
        "future_provider_route": "future explicit physical storage execution tasks",
        "target_acceptance_mode": "storage_physical_execution_and_promotion",
        "required_evidence": [
            "scope-bound physical execution request",
            "schema migration execution evidence",
            "partition migration execution evidence",
            "dataset manifest write/validate evidence",
            "compaction/cache TTL/artifact cleanup evidence",
            "durable promotion review",
        ],
        "not_allowed_next_steps": [
            "write Parquet from cache render",
            "delete artifacts from cache render",
            "treat execution request as physical execution",
            "mark production storage complete from local receipts",
        ],
    },
    {
        "queue_id": "p4_worker_runtime_qa",
        "priority": "P4",
        "ltg_ids": ["LTG-06"],
        "action_label": "Bind Worker runtime QA scope evidence",
        "mode_layer": "button_task_then_manual_worker_runtime_qa",
        "current_phase": "runtime_qa_scope_ticket_required",
        "first_allowed_route": "POST /api/worker/synthetic-healthcheck",
        "second_allowed_route": "POST /api/worker/runtime-qa-execution-request",
        "future_provider_route": "future explicit worker runtime QA execution task",
        "target_acceptance_mode": "worker_runtime_qa_and_promotion",
        "required_evidence": [
            "synthetic local task-store healthcheck",
            "activation review",
            "production evidence plan",
            "runtime QA execution request",
            "runtime QA dry-run",
            "real Celery/Redis runtime QA evidence",
        ],
        "not_allowed_next_steps": [
            "start Celery from cache render",
            "ping Redis from cache render",
            "dispatch provider/model tasks from runtime QA tickets",
            "mark production worker complete from local receipts",
        ],
    },
    {
        "queue_id": "p5_deepseek_provider_benchmark_scope",
        "priority": "P5",
        "ltg_ids": ["LTG-07"],
        "action_label": "Bind DeepSeek provider benchmark scope ticket",
        "mode_layer": "button_task_then_model_execution",
        "current_phase": "provider_benchmark_scope_ticket_required",
        "first_allowed_route": "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket",
        "second_allowed_route": "",
        "future_provider_route": "future explicit DeepSeek provider benchmark task",
        "target_acceptance_mode": "deepseek_provider_benchmark_and_promotion",
        "required_evidence": [
            "approved provider benchmark scope ticket",
            "server-side secret presence boolean only",
            "provider benchmark model ledger",
            "provider response_format/json_schema execution evidence",
            "bounded retry/repair evidence",
            "token/cost/redaction durable evidence",
        ],
        "not_allowed_next_steps": [
            "call DeepSeek from GET cache",
            "call DeepSeek from React render",
            "treat scope ticket as provider benchmark evidence",
            "override numeric values or strategy action",
        ],
    },
    {
        "queue_id": "p5_next_session_map_browser_qa",
        "priority": "P5",
        "ltg_ids": ["LTG-08"],
        "action_label": "Review ECharts next-session browser QA evidence",
        "mode_layer": "button_task_then_browser_or_parity_execution",
        "current_phase": "browser_qa_review_required",
        "first_allowed_route": "POST /api/next-session/browser-qa-review",
        "second_allowed_route": "",
        "future_provider_route": "future explicit next-session parity and production replacement tasks",
        "target_acceptance_mode": "next_session_browser_visual_performance_and_parity_promotion",
        "required_evidence": [
            "same-packet Streamlit parity evidence",
            "browser visual QA report",
            "browser performance trace",
            "reduced-motion evidence",
            "durable CI/release evidence",
            "production replacement promotion review",
        ],
        "not_allowed_next_steps": [
            "open browser from GET cache",
            "treat local review as browser execution",
            "retire Streamlit visual path before parity evidence",
            "compute action or mutate operation_zones in React",
        ],
    },
    {
        "queue_id": "p6_tauri_package_readiness_review",
        "priority": "P6",
        "ltg_ids": ["LTG-09"],
        "action_label": "Review Tauri package readiness receipts",
        "mode_layer": "cache_receipt_then_manual_packaged_runtime_qa",
        "current_phase": "package_readiness_and_durable_evidence_visible",
        "first_allowed_route": "GET /api/desktop/preflight-cache",
        "second_allowed_route": "",
        "future_provider_route": "future explicit Tauri build and packaged runtime QA",
        "target_acceptance_mode": "tauri_packaged_runtime_build_launch_and_offline_ux_promotion",
        "required_evidence": [
            "production package readiness receipt",
            "durable evidence recipe",
            "repeatable tauri build log",
            "packaged app launch QA",
            "backend-offline packaged UX proof",
            "signing/notarization or local distribution decision",
        ],
        "not_allowed_next_steps": [
            "run npm/cargo/Tauri from GET cache",
            "open packaged app from React render",
            "treat release artifact detection as packaged runtime QA",
            "mark LTG-09 complete from preflight receipts",
        ],
    },
    {
        "queue_id": "p7_streamlit_retirement_review",
        "priority": "P7",
        "ltg_ids": ["LTG-10"],
        "action_label": "Review Streamlit retirement readiness receipts",
        "mode_layer": "cache_receipt_then_manual_retirement_review",
        "current_phase": "fallback_blockers_and_durable_evidence_visible",
        "first_allowed_route": "GET /api/legacy/cache",
        "second_allowed_route": "",
        "future_provider_route": "future explicit replacement parity and Streamlit fallback retirement review",
        "target_acceptance_mode": "streamlit_primary_workflow_exit_and_fallback_retirement",
        "required_evidence": [
            "ordinary workflow replacement parity",
            "legacy fallback dependency inventory",
            "retirement readiness receipt",
            "durable retirement evidence recipe",
            "admin/debug fallback decision",
            "guardrail regression proof",
        ],
        "not_allowed_next_steps": [
            "open Streamlit from GET cache",
            "run legacy tools from React render",
            "delete app.py before replacement parity",
            "treat local receipt as Streamlit retirement completion",
        ],
    },
    {
        "queue_id": "p8_motion_production_promotion_review",
        "priority": "P8",
        "ltg_ids": ["LTG-14"],
        "action_label": "Review motion production promotion receipts",
        "mode_layer": "button_task_then_browser_or_release_evidence_promotion",
        "current_phase": "local_browser_review_and_promotion_scope_required",
        "first_allowed_route": "POST /api/audit/motion-browser-qa-review",
        "second_allowed_route": "POST /api/audit/motion-production-promotion-dry-run",
        "future_provider_route": "future explicit visual/performance promotion and durable CI/release evidence",
        "target_acceptance_mode": "motion_visual_performance_durable_promotion",
        "required_evidence": [
            "local browser QA artifact review",
            "motion production activation receipt",
            "promotion dry-run scope ticket",
            "durable visual QA evidence",
            "performance trace/budget evidence",
            "CI or release evidence",
        ],
        "not_allowed_next_steps": [
            "open browser from GET audit cache",
            "treat ignored local artifacts as durable CI evidence",
            "call GitHub API from motion promotion dry-run",
            "use motion to imply trade urgency or strategy action",
        ],
    },
    {
        "queue_id": "p0_release_gate_push_readiness",
        "priority": "P0",
        "ltg_ids": ["LTG-11"],
        "action_label": "Review release gate and push-readiness receipts",
        "mode_layer": "cache_receipt_then_fresh_local_gate_and_remote_ci",
        "current_phase": "local_gate_ready_remote_ci_and_fresh_run_required",
        "first_allowed_route": "GET /api/audit/cache",
        "second_allowed_route": "",
        "future_provider_route": "fresh local push gate plus remote CI verification",
        "target_acceptance_mode": "repeatable_release_gate_and_ci_green_evidence",
        "required_evidence": [
            "fresh local gate run",
            "frontend build and smoke evidence",
            "secret and artifact scan evidence",
            "remote CI status for pushed head",
            "failure email triage against matching head/logs",
            "explicit user push confirmation",
        ],
        "not_allowed_next_steps": [
            "call GitHub API from GET audit cache",
            "treat old local gate metadata as current release approval",
            "push from queue render",
            "dismiss failure emails without matching head/logs",
        ],
    },
    {
        "queue_id": "p10_trade_isolation_release_guard",
        "priority": "P10",
        "ltg_ids": ["LTG-12"],
        "action_label": "Keep real-trading isolation visible as a release invariant",
        "mode_layer": "cache_receipt_then_separate_real_trading_project",
        "current_phase": "research_client_release_receipt_ready_real_trading_still_disconnected",
        "first_allowed_route": "GET /api/risk/cache",
        "second_allowed_route": "",
        "future_provider_route": "separate approved real-trading integration project only",
        "target_acceptance_mode": "continued_no_broker_no_order_no_action_mutation_invariant",
        "required_evidence": [
            "continued no-broker proof",
            "continued no-order-endpoint proof",
            "continued no-frontend-submit proof",
            "continued no-model-action-mutation proof",
            "release receipt remains research-only",
            "separate project approval before any real trading",
        ],
        "not_allowed_next_steps": [
            "treat release receipt as trading approval",
            "connect broker adapter inside Command Center 3 migration",
            "add order endpoint to cache/task API",
            "let model or factor output become orders",
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
    "p3_factor_universe_worker_batch_research": [
        {
            "phase_key": "factor_universe_worker_batch_dry_run_scope_ticket",
            "task_type": "run_factor_universe_worker_batch_dry_run",
            "receipt_key": "universe_worker_batch_dry_run_receipt",
            "route": "POST /api/factor-quant/universe-worker-batch-dry-run",
        },
        {
            "phase_key": "factor_universe_worker_batch_execution_recipe",
            "task_type": "",
            "receipt_key": "universe_worker_batch_execution_recipe",
            "route": "GET /api/factor-quant/cache",
        },
        {
            "phase_key": "factor_universe_worker_batch_execution_request_ticket",
            "task_type": "run_factor_universe_worker_batch_execution_request",
            "receipt_key": "universe_worker_batch_execution_request_receipt",
            "route": "POST /api/factor-quant/universe-worker-batch-execution-request",
        },
        {
            "phase_key": "factor_universe_worker_batch_local_research_receipt",
            "task_type": "run_factor_universe_worker_batch_research",
            "receipt_key": "universe_worker_batch_research_receipt",
            "route": "POST /api/factor-quant/universe-worker-batch-research",
        },
        {
            "phase_key": "factor_universe_durable_evidence_recipe",
            "task_type": "",
            "receipt_key": "universe_durable_evidence_recipe",
            "route": "GET /api/factor-quant/cache",
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
        {
            "phase_key": "radar_legacy_retirement_review_receipt",
            "task_type": "run_candidate_radar_legacy_retirement_review",
            "receipt_key": "candidate_radar_legacy_retirement_review_receipt",
            "route": "POST /api/candidate-radar/legacy-retirement-review",
        },
        {
            "phase_key": "radar_production_promotion_review_receipt",
            "task_type": "run_candidate_radar_production_promotion_review",
            "receipt_key": "candidate_radar_production_promotion_review_receipt",
            "route": "POST /api/candidate-radar/production-promotion-review",
        },
    ],
    "p4_storage_physical_execution": [
        {
            "phase_key": "storage_backtest_results_schema_seed_receipt",
            "task_type": "run_storage_backtest_results_schema_seed",
            "receipt_key": "backtest_results_schema_seed_evidence",
            "route": "POST /api/storage/backtest-results/schema-seed",
        },
        {
            "phase_key": "storage_schema_validation_acceptance_receipt",
            "task_type": "run_storage_schema_validation_acceptance",
            "receipt_key": "schema_validation_acceptance_evidence",
            "route": "POST /api/storage/schema-validation/acceptance",
        },
        {
            "phase_key": "storage_dataset_version_manifest_dry_run_receipt",
            "task_type": "run_storage_dataset_version_manifest_dry_run",
            "receipt_key": "storage_dataset_version_manifest_dry_run",
            "route": "POST /api/storage/dataset-version-manifest/dry-run",
        },
        {
            "phase_key": "storage_dataset_version_manifest_review_receipt",
            "task_type": "run_storage_dataset_version_manifest_review",
            "receipt_key": "storage_dataset_version_manifest_review",
            "route": "POST /api/storage/dataset-version-manifest/review",
        },
        {
            "phase_key": "storage_dataset_version_manifest_write_receipt",
            "task_type": "run_storage_dataset_version_manifest_write",
            "receipt_key": "storage_dataset_version_manifest_write",
            "route": "POST /api/storage/dataset-version-manifest/write",
        },
        {
            "phase_key": "storage_dataset_version_manifest_validate_receipt",
            "task_type": "run_storage_dataset_version_manifest_validate",
            "receipt_key": "storage_dataset_version_manifest_validate",
            "route": "POST /api/storage/dataset-version-manifest/validate",
        },
        {
            "phase_key": "storage_physical_execution_request_ticket",
            "task_type": "run_storage_physical_execution_request",
            "receipt_key": "storage_physical_execution_request",
            "route": "POST /api/storage/physical-execution-request",
        },
    ],
    "p4_worker_runtime_qa": [
        {
            "phase_key": "worker_synthetic_healthcheck_receipt",
            "task_type": "run_worker_synthetic_healthcheck",
            "receipt_key": "worker_synthetic_healthcheck",
            "route": "POST /api/worker/synthetic-healthcheck",
        },
        {
            "phase_key": "worker_activation_review_receipt",
            "task_type": "run_worker_activation_review",
            "receipt_key": "worker_activation_review_task_receipt",
            "route": "POST /api/worker/activation-review",
        },
        {
            "phase_key": "worker_production_evidence_plan_receipt",
            "task_type": "run_worker_production_evidence_plan",
            "receipt_key": "worker_production_evidence_plan_receipt",
            "route": "POST /api/worker/production-evidence-plan",
        },
        {
            "phase_key": "worker_runtime_qa_execution_request_ticket",
            "task_type": "run_worker_runtime_qa_execution_request",
            "receipt_key": "worker_runtime_qa_execution_request_receipt",
            "route": "POST /api/worker/runtime-qa-execution-request",
        },
        {
            "phase_key": "worker_runtime_qa_dry_run_receipt",
            "task_type": "run_worker_runtime_qa_dry_run",
            "receipt_key": "worker_runtime_qa_dry_run_receipt",
            "route": "POST /api/worker/runtime-qa-dry-run",
        },
    ],
    "p5_deepseek_provider_benchmark_scope": [
        {
            "phase_key": "deepseek_provider_benchmark_scope_ticket",
            "task_type": "run_deepseek_provider_benchmark_scope_ticket",
            "receipt_key": "deepseek_provider_benchmark_scope_ticket_receipt",
            "route": "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket",
        },
    ],
    "p5_next_session_map_browser_qa": [
        {
            "phase_key": "next_session_browser_qa_review_receipt",
            "task_type": "run_next_session_browser_qa_review",
            "receipt_key": "next_session_browser_qa_review_contract",
            "route": "POST /api/next-session/browser-qa-review",
        },
    ],
    "p6_tauri_package_readiness_review": [
        {
            "phase_key": "tauri_production_package_readiness_receipt",
            "task_type": "",
            "receipt_key": "production_package_readiness_receipt",
            "route": "GET /api/desktop/preflight-cache",
        },
        {
            "phase_key": "tauri_package_durable_evidence_recipe",
            "task_type": "",
            "receipt_key": "tauri_package_durable_evidence_recipe",
            "route": "GET /api/desktop/preflight-cache",
        },
    ],
    "p7_streamlit_retirement_review": [
        {
            "phase_key": "streamlit_retirement_readiness_receipt",
            "task_type": "",
            "receipt_key": "streamlit_retirement_readiness_receipt",
            "route": "GET /api/legacy/cache",
        },
        {
            "phase_key": "streamlit_retirement_durable_evidence_recipe",
            "task_type": "",
            "receipt_key": "streamlit_retirement_durable_evidence_recipe",
            "route": "GET /api/legacy/cache",
        },
    ],
    "p8_motion_production_promotion_review": [
        {
            "phase_key": "motion_production_activation_receipt",
            "task_type": "",
            "receipt_key": "motion_production_activation_receipt",
            "route": "GET /api/audit/cache",
        },
        {
            "phase_key": "motion_browser_qa_review_receipt",
            "task_type": "run_motion_browser_qa_review",
            "receipt_key": "motion_browser_qa_review_contract",
            "route": "POST /api/audit/motion-browser-qa-review",
        },
        {
            "phase_key": "motion_production_promotion_dry_run_ticket",
            "task_type": "run_motion_production_promotion_dry_run",
            "receipt_key": "motion_promotion_dry_run_receipt",
            "route": "POST /api/audit/motion-production-promotion-dry-run",
        },
        {
            "phase_key": "motion_durable_evidence_recipe",
            "task_type": "",
            "receipt_key": "motion_durable_evidence_recipe",
            "route": "GET /api/audit/cache",
        },
    ],
    "p0_release_gate_push_readiness": [
        {
            "phase_key": "release_gate_readiness_audit",
            "task_type": "",
            "receipt_key": "release_gate_readiness_audit",
            "route": "GET /api/audit/cache",
        },
        {
            "phase_key": "ci_notification_triage_contract",
            "task_type": "",
            "receipt_key": "ci_notification_triage_contract",
            "route": "GET /api/audit/cache",
        },
        {
            "phase_key": "release_gate_push_readiness_receipt",
            "task_type": "",
            "receipt_key": "release_gate_push_readiness_receipt",
            "route": "GET /api/audit/cache",
        },
    ],
    "p10_trade_isolation_release_guard": [
        {
            "phase_key": "trade_isolation_release_receipt",
            "task_type": "",
            "receipt_key": "trade_isolation_release_receipt",
            "route": "GET /api/risk/cache",
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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _latest_tushare_direct_provider_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import data_health_service

        packet = data_health_service.read_data_health_timeline_cache()
    except Exception:
        packet = {}
    if not isinstance(packet, dict):
        packet = {}
    summary = _dict_or_empty(packet.get("local_tushare_refresh_packet_summary"))
    promotion = _dict_or_empty(packet.get("trade_cal_provider_acceptance_promotion_audit"))
    selected_apis = [str(item) for item in summary.get("selected_apis") or []]
    trade_cal_provider_call_count = int(summary.get("trade_cal_provider_call_ledger_observed_count") or 0)
    call_ledger_count = int(summary.get("call_ledger_count") or 0)
    trade_cal_safe_fields = promotion.get("safe_call_ledger_fields_present") is True
    return {
        "schema_version": "migration_tushare_direct_provider_evidence_summary.v1",
        "source_packet_key": summary.get("source_packet_key") or "command_center_tushare_refresh_packet",
        "source_status": summary.get("status") or "missing",
        "available": summary.get("available") is True,
        "selected_apis": selected_apis,
        "selected_api_count": len(selected_apis),
        "call_ledger_count": call_ledger_count,
        "trade_cal_call_ledger_count": int(summary.get("trade_cal_call_ledger_count") or 0),
        "trade_cal_provider_call_ledger_observed_count": trade_cal_provider_call_count,
        "trade_cal_provider_observed_row_count": int(summary.get("trade_cal_provider_observed_row_count") or 0),
        "trade_cal_provider_call_statuses": [
            str(item) for item in summary.get("trade_cal_provider_call_statuses") or []
        ],
        "trade_cal_provider_call_ledger_evidence_done": bool(trade_cal_provider_call_count and trade_cal_safe_fields),
        "provider_call_ledger_evidence_done": bool(call_ledger_count),
        "full_interface_selection_done": len(selected_apis) >= 17,
        "provider_backed_long_window_acceptance_done": summary.get("provider_backed_long_window_acceptance_done")
        is True,
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "trade_cal_promotion_status": promotion.get("status") or "missing",
        "trade_cal_promotion_ready": promotion.get("promotion_ready") is True,
        "safe_trade_cal_call_ledger_fields_present": trade_cal_safe_fields,
        "trade_cal_promotion_blocker_count": int(promotion.get("blocking_criterion_count") or 0),
        "direct_evidence_layer": "L3_direct_provider_call_ledger" if call_ledger_count else "L1_static_contract",
        "cache_only": True,
        "read_only_sqlite_packet_lookup": True,
        "external_calls_triggered": False,
        "tushare_called_by_lookup": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _latest_factor_test_lab_direct_research_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import factor_service

        packet = factor_service.read_factor_quant_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    factor_tests = _dict_or_empty(packet_map.get("factor_tests"))
    acceptance = _dict_or_empty(factor_tests.get("acceptance_contract"))
    dry_run = _dict_or_empty(factor_tests.get("provider_small_pool_acceptance_dry_run_receipt"))
    recipe = _dict_or_empty(factor_tests.get("provider_small_pool_execution_recipe"))
    request = _dict_or_empty(factor_tests.get("provider_small_pool_execution_request_receipt"))
    items = factor_tests.get("items") if isinstance(factor_tests.get("items"), list) else []

    task_rows = _task_statuses_by_type()

    def _task_receipt(task_type: str, receipt_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for task in task_rows.get(task_type, []):
            payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
            receipt = payload_safe.get(receipt_key) if isinstance(payload_safe, dict) else {}
            receipt_map = _dict_or_empty(receipt)
            status = str(receipt_map.get("status") or "")
            if status and not status.endswith("_missing"):
                if "contains_secret" not in receipt_map:
                    receipt_map["contains_secret"] = False
                return receipt_map, dict(payload_safe)
        return {}, {}

    dry_run_payload: dict[str, Any] = {}
    request_payload: dict[str, Any] = {}
    if (
        dry_run.get("schema_version") != "factor_test_provider_small_pool_acceptance_dry_run.v1"
        or str(dry_run.get("status") or "").endswith("_missing")
        or dry_run.get("local_dry_run_ready") is not True
    ):
        dry_run, dry_run_payload = _task_receipt(
            "run_factor_test_provider_small_pool_acceptance_dry_run",
            "provider_small_pool_acceptance_dry_run_receipt",
        )
    if (
        request.get("schema_version") != "factor_test_provider_small_pool_execution_request.v1"
        or str(request.get("status") or "").endswith("_missing")
        or request.get("local_execution_request_ready") is not True
    ):
        request, request_payload = _task_receipt(
            "run_factor_test_provider_small_pool_execution_request",
            "provider_small_pool_execution_request_receipt",
        )
    if not request_payload and request:
        request_payload = {
            "execution_recipe_status": request.get("execution_recipe_status"),
            "execution_recipe_ready": False,
            "scope_ticket_ready": False,
        }
    recipe_ready_from_task = (
        str(request_payload.get("execution_recipe_status") or "")
        == "factor_test_provider_small_pool_execution_recipe_ready_execution_pending"
        and request_payload.get("execution_recipe_ready") is True
        and request_payload.get("scope_ticket_ready") is True
    )
    if recipe.get("local_recipe_ready") is not True and recipe_ready_from_task:
        recipe = {
            "schema_version": "factor_test_provider_small_pool_execution_recipe.v1",
            "status": "factor_test_provider_small_pool_execution_recipe_ready_execution_pending",
            "local_recipe_ready": True,
            "scope_ticket_ready": True,
            "provider_execution_implemented": False,
            "provider_backed_small_pool_validation_done": False,
            "production_factor_test_validation_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "acceptance_scope_hash_short": request.get("acceptance_scope_hash_short") or "",
        }

    packet_safe = bool(
        packet_map.get("external_calls_triggered") is False
        and packet_map.get("tushare_called") is False
        and packet_map.get("deepseek_called") is False
        and packet_map.get("github_called") is False
        and packet_map.get("does_not_execute_trades") is True
        and packet_map.get("does_not_modify_strategy_action") is True
        and packet_map.get("contains_secret") is not True
    )
    metric_rows_with_values = [
        row
        for row in items
        if isinstance(row, dict)
        and row.get("data_status") not in {"metric_scaffold_only", "not_enough_data"}
        and any(
            row.get(key) is not None
            for key in (
                "ic",
                "rank_ic",
                "icir",
                "group_return",
                "top_bottom",
                "max_drawdown",
                "neutral_ic",
                "out_of_sample_decay",
                "cost_model",
            )
        )
    ]
    local_light_metric_baseline = bool(
        packet_safe
        and int(factor_tests.get("computed_item_count") or 0) > 0
        and bool(metric_rows_with_values)
        and factor_tests.get("external_calls_triggered") is False
        and factor_tests.get("tushare_called") is False
        and factor_tests.get("deepseek_called") is False
        and factor_tests.get("github_called") is False
        and factor_tests.get("does_not_execute_trades") is True
        and factor_tests.get("does_not_modify_strategy_action") is True
    )
    provider_small_pool_scope_ticket = bool(
        packet_safe
        and dry_run.get("schema_version") == "factor_test_provider_small_pool_acceptance_dry_run.v1"
        and dry_run.get("local_dry_run_ready") is True
        and dry_run.get("preflight_ready_for_user_approved_real_task") is True
        and dry_run.get("provider_execution_implemented") is False
        and dry_run.get("provider_backed_small_pool_validation_done") is False
        and dry_run.get("production_factor_test_validation_complete") is False
        and dry_run.get("external_calls_triggered") is False
        and dry_run.get("tushare_called") is False
        and dry_run.get("deepseek_called") is False
        and dry_run.get("github_called") is False
        and dry_run.get("does_not_execute_trades") is True
        and dry_run.get("does_not_modify_strategy_action") is True
        and dry_run.get("contains_secret") is False
        and recipe.get("schema_version") == "factor_test_provider_small_pool_execution_recipe.v1"
        and recipe.get("local_recipe_ready") is True
        and recipe.get("scope_ticket_ready") is True
        and recipe.get("provider_execution_implemented") is False
        and recipe.get("provider_backed_small_pool_validation_done") is False
        and recipe.get("production_factor_test_validation_complete") is False
        and recipe.get("external_calls_triggered") is False
        and recipe.get("tushare_called") is False
        and recipe.get("deepseek_called") is False
        and recipe.get("github_called") is False
        and recipe.get("does_not_execute_trades") is True
        and recipe.get("does_not_modify_strategy_action") is True
        and recipe.get("contains_secret") is False
        and request.get("schema_version") == "factor_test_provider_small_pool_execution_request.v1"
        and request.get("local_execution_request_ready") is True
        and request.get("ready_for_manual_provider_task_submission") is True
        and request.get("provider_execution_implemented") is False
        and request.get("provider_call_ledger_evidence_done") is False
        and request.get("provider_backed_small_pool_validation_done") is False
        and request.get("production_factor_test_validation_complete") is False
        and request.get("external_calls_triggered") is False
        and request.get("tushare_called") is False
        and request.get("deepseek_called") is False
        and request.get("github_called") is False
        and request.get("does_not_execute_trades") is True
        and request.get("does_not_modify_strategy_action") is True
        and request.get("contains_secret") is False
    )
    direct_stage_keys = []
    if local_light_metric_baseline:
        direct_stage_keys.append("local_light_metric_baseline")
    if provider_small_pool_scope_ticket:
        direct_stage_keys.append("provider_small_pool_scope_ticket")
    scope_hash_short = (
        request.get("acceptance_scope_hash_short")
        or dry_run.get("acceptance_scope_hash_short")
        or recipe.get("acceptance_scope_hash_short")
        or ""
    )
    return {
        "schema_version": "migration_factor_test_lab_direct_research_evidence_summary.v1",
        "source_packet_key": "command_center_factor_quant_hub_packet",
        "status": "factor_test_lab_direct_evidence_visible_production_pending"
        if direct_stage_keys
        else "factor_test_lab_direct_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "local_light_metric_baseline_verified": local_light_metric_baseline,
        "provider_small_pool_scope_ticket_verified": provider_small_pool_scope_ticket,
        "provider_small_pool_dry_run_ready": dry_run.get("local_dry_run_ready") is True,
        "provider_small_pool_execution_recipe_ready": recipe.get("local_recipe_ready") is True,
        "provider_small_pool_execution_request_ready": request.get("local_execution_request_ready") is True,
        "provider_small_pool_scope_hash_short": scope_hash_short,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
        "provider_execution_implemented": False,
        "provider_call_ledger_evidence_done": False,
        "metrics_remain_research_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_factor_test_scope_evidence"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "factor_test_scope_direct_evidence_is_not_provider_validation_or_production_completion",
    }


def _latest_factor_universe_direct_research_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import factor_service

        packet = factor_service.read_factor_quant_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    contract = _dict_or_empty(packet_map.get("universe_research_contract"))
    rank_zscore = _dict_or_empty(packet_map.get("universe_local_rank_zscore_dry_run"))
    worker_receipt = _dict_or_empty(packet_map.get("universe_worker_batch_research_receipt"))

    packet_safe = bool(
        packet_map.get("external_calls_triggered") is False
        and packet_map.get("tushare_called") is False
        and packet_map.get("deepseek_called") is False
        and packet_map.get("github_called") is False
        and packet_map.get("does_not_execute_trades") is True
        and packet_map.get("does_not_modify_strategy_action") is True
        and packet_map.get("contains_secret") is not True
    )
    local_rank_zscore_done = bool(
        packet_safe
        and rank_zscore.get("schema_version") == "factor_universe_local_rank_zscore_dry_run.v1"
        and rank_zscore.get("status") == "local_rank_zscore_dry_run_ready_research_only"
        and rank_zscore.get("rank_zscore_dry_run_executed") is True
        and int(rank_zscore.get("eligible_group_count") or 0) > 0
        and int(rank_zscore.get("rank_zscore_preview_row_count") or 0) > 0
        and rank_zscore.get("metrics_are_research_only") is True
        and rank_zscore.get("cross_sectional_rank_zscore_done") is False
        and rank_zscore.get("neutralization_done") is False
        and rank_zscore.get("large_universe_pipeline_done") is False
        and rank_zscore.get("full_pool_validation_done") is False
        and rank_zscore.get("production_factor_universe_complete") is False
        and rank_zscore.get("page_render_starts_full_pool") is False
        and rank_zscore.get("frontend_computes_rank_zscore") is False
        and rank_zscore.get("partial_pool_is_full_market_proof") is False
        and rank_zscore.get("external_calls_triggered") is False
        and rank_zscore.get("tushare_called") is False
        and rank_zscore.get("deepseek_called") is False
        and rank_zscore.get("github_called") is False
        and rank_zscore.get("does_not_execute_trades") is True
        and rank_zscore.get("does_not_modify_strategy_action") is True
    )
    worker_research_receipt_ready = bool(
        worker_receipt.get("schema_version") == "factor_universe_worker_batch_research_receipt.v1"
        and worker_receipt.get("local_worker_research_receipt_ready") is True
        and worker_receipt.get("ready_for_worker_runtime_evidence_collection") is True
        and worker_receipt.get("local_worker_task_record_created") is True
        and worker_receipt.get("worker_task_created") is False
        and worker_receipt.get("worker_task_executed") is False
        and worker_receipt.get("worker_execution_implemented") is False
    )
    direct_stage_keys = []
    if local_rank_zscore_done:
        direct_stage_keys.append("local_rank_zscore_research_preview")
    return {
        "schema_version": "migration_factor_universe_direct_research_evidence_summary.v1",
        "source_packet_key": "command_center_factor_quant_hub_packet",
        "status": "factor_universe_direct_research_evidence_visible_production_pending"
        if direct_stage_keys
        else "factor_universe_direct_research_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "local_rank_zscore_research_preview_verified": local_rank_zscore_done,
        "local_rank_zscore_status": str(rank_zscore.get("status") or "missing"),
        "local_rank_zscore_preview_row_count": int(rank_zscore.get("rank_zscore_preview_row_count") or 0),
        "local_rank_zscore_eligible_group_count": int(rank_zscore.get("eligible_group_count") or 0),
        "local_rank_zscore_usable_row_count": int(rank_zscore.get("usable_row_count") or 0),
        "worker_batch_research_receipt_ready": worker_research_receipt_ready,
        "worker_batch_research_receipt_is_not_worker_execution": worker_research_receipt_ready,
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
        "partial_pool_is_full_market_proof": False,
        "metrics_remain_research_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "contract_worker_batch_research_receipt_ready": contract.get("worker_batch_research_receipt_ready") is True,
        "direct_evidence_layer": "L3_local_factor_universe_research_preview"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "factor_universe_local_rank_zscore_preview_is_not_worker_backed_or_full_pool_validation",
    }


def _latest_release_gate_direct_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import audit_service

        receipt = audit_service._read_local_push_gate_run_receipt()
    except Exception:
        receipt = {}
    receipt_map = receipt if isinstance(receipt, dict) else {}
    checks = [str(item) for item in receipt_map.get("checks") or []]
    required_checks = {
        "python_unittest",
        "desktop_build",
        "command_center_3_smoke",
        "diff_whitespace_check",
        "high_risk_secret_scan",
        "secret_keyword_review_contract",
        "generated_artifact_scan",
        "clean_worktree_check",
    }
    fresh_gate_run_done = bool(
        receipt_map.get("schema_version") == "command_center_3_local_push_gate_run_receipt.v1"
        and receipt_map.get("status") == "local_push_gate_passed_current_head"
        and receipt_map.get("fresh_local_gate_run_observed") is True
        and receipt_map.get("head_matches_current") is True
        and required_checks.issubset(set(checks))
        and receipt_map.get("did_not_push") is True
        and receipt_map.get("git_add_dot_used") is False
        and receipt_map.get("github_api_called") is False
        and receipt_map.get("external_calls_triggered") is False
        and receipt_map.get("tushare_called") is False
        and receipt_map.get("deepseek_called") is False
        and receipt_map.get("github_called") is False
        and receipt_map.get("does_not_execute_trades") is True
        and receipt_map.get("does_not_modify_strategy_action") is True
        and receipt_map.get("contains_secret") is False
        and receipt_map.get("local_gate_pass_is_not_ci_status") is True
        and receipt_map.get("remote_actions_status_known") is False
        and receipt_map.get("latest_remote_run_verified_green") is False
    )
    direct_stage_keys = ["fresh_local_gate_command_run"] if fresh_gate_run_done else []
    return {
        "schema_version": "migration_release_gate_direct_evidence_summary.v1",
        "source_packet_key": "local_push_gate_run_receipt",
        "source_status": str(receipt_map.get("status") or "missing"),
        "status": "release_gate_direct_evidence_visible_remote_ci_pending"
        if direct_stage_keys
        else "release_gate_direct_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "fresh_local_gate_run_observed": fresh_gate_run_done,
        "local_push_gate_receipt_head_matches_current": receipt_map.get("head_matches_current") is True,
        "local_push_gate_receipt_head": str(receipt_map.get("head") or ""),
        "local_push_gate_receipt_current_head": str(receipt_map.get("current_head") or ""),
        "local_push_gate_check_count": len(checks),
        "required_local_gate_checks_present": required_checks.issubset(set(checks)),
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
        "release_gate_complete": False,
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
        "direct_evidence_layer": "L3_local_release_gate_execution_evidence"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "fresh_local_push_gate_direct_evidence_is_not_remote_ci_or_push_completion",
    }


def _local_receipt_packet_fallback(queue_id: str, receipt_key: str) -> dict[str, Any]:
    source = ""
    source_packet_key = ""
    storage_source = "sqlite_meta_packet"
    if queue_id == "p3_factor_universe_worker_batch_research":
        try:
            from server.services import factor_service

            packet = factor_service.read_factor_quant_cache()
        except Exception:
            packet = {}
        source = "factor_quant_cache_packet"
        source_packet_key = "command_center_factor_quant_hub_packet"
    elif queue_id == "p3_candidate_radar_provider_worker_promotion":
        try:
            from server.services import candidate_service

            packet = candidate_service.read_candidate_radar_cache()
        except Exception:
            packet = {}
        source = "candidate_radar_cache_packet"
        source_packet_key = "command_center_3_candidate_radar_cache"
    elif queue_id == "p4_storage_physical_execution":
        try:
            from server.services import storage_service

            packet = storage_service.storage_overview()
        except Exception:
            packet = {}
        source = "storage_overview_packet"
        source_packet_key = "command_center_3_storage_overview"
    elif queue_id == "p4_worker_runtime_qa":
        try:
            from server.services import worker_service

            packet = worker_service.read_worker_runtime_cache()
        except Exception:
            packet = {}
        source = "worker_runtime_cache_packet"
        source_packet_key = "command_center_3_worker_runtime_cache"
    elif queue_id == "p5_deepseek_provider_benchmark_scope":
        try:
            from server.services import factor_service

            packet = factor_service.read_factor_quant_cache()
        except Exception:
            packet = {}
        source = "factor_quant_cache_packet"
        source_packet_key = "command_center_factor_quant_hub_packet"
    elif queue_id == "p5_next_session_map_browser_qa":
        try:
            from server.services import next_session_service

            packet = next_session_service.read_next_session_cache()
        except Exception:
            packet = {}
        source = "next_session_cache_packet"
        source_packet_key = "command_center_next_session_projection_packet"
    elif queue_id == "p6_tauri_package_readiness_review":
        try:
            from server.services import desktop_service

            packet = desktop_service.read_desktop_shell_preflight_cache()
        except Exception:
            packet = {}
        source = "desktop_shell_preflight_cache_packet"
        source_packet_key = "command_center_3_desktop_shell_preflight_cache"
    elif queue_id == "p7_streamlit_retirement_review":
        try:
            from server.services import legacy_service

            packet = legacy_service.read_legacy_bridge_cache()
        except Exception:
            packet = {}
        source = "legacy_bridge_cache_packet"
        source_packet_key = "command_center_3_legacy_bridge_cache"
    elif queue_id == "p8_motion_production_promotion_review":
        try:
            from server.services import audit_service
            from storage.sqlite_meta import SQLiteMetaStore

            packet = SQLiteMetaStore(audit_service.SQLITE_META_PATH).read_packet(
                "command_center_3_call_ledger_audit_cache"
            )
        except Exception:
            packet = {}
        source = "call_ledger_audit_sqlite_packet"
        source_packet_key = "command_center_3_call_ledger_audit_cache"
    elif queue_id == "p0_release_gate_push_readiness":
        try:
            from server.services import audit_service

            release_gate, _, workflow_rows = audit_service._release_gate_readiness_audit()
            release_gate = release_gate if isinstance(release_gate, dict) else {}
            ci_triage_contract, _ = audit_service._ci_notification_triage_contract(release_gate, workflow_rows)
            ci_triage_contract = ci_triage_contract if isinstance(ci_triage_contract, dict) else {}
            local_gate_run_receipt = audit_service._read_local_push_gate_run_receipt()
            push_receipt, _ = audit_service._release_gate_push_readiness_receipt(
                release_gate,
                ci_triage_contract,
                local_gate_run_receipt,
            )
            packet = {
                "release_gate_readiness_audit": release_gate,
                "ci_notification_triage_contract": ci_triage_contract,
                "local_push_gate_run_receipt": local_gate_run_receipt,
                "release_gate_push_readiness_receipt": push_receipt if isinstance(push_receipt, dict) else {},
            }
        except Exception:
            packet = {}
        source = "audit_release_gate_static_helpers"
        source_packet_key = "command_center_3_call_ledger_audit_cache"
        storage_source = "local_static_contract"
    elif queue_id == "p10_trade_isolation_release_guard":
        try:
            from server.services import risk_service

            packet = risk_service.read_risk_guardrails_cache()
        except Exception:
            packet = {}
        source = "risk_guardrails_cache_packet"
        source_packet_key = "command_center_3_risk_guardrails_cache"
    else:
        return {}
    packet_map = packet if isinstance(packet, dict) else {}
    receipt = packet_map.get(receipt_key)
    if (not isinstance(receipt, dict) or not receipt) and queue_id == "p4_storage_physical_execution":
        storage_packet_keys = {
            "storage_dataset_version_manifest_dry_run": "command_center_3_storage_dataset_version_manifest_dry_run_packet",
            "storage_dataset_version_manifest_review": "command_center_3_storage_dataset_version_manifest_review_packet",
            "storage_dataset_version_manifest_write": "command_center_3_storage_dataset_version_manifest_write_packet",
            "storage_dataset_version_manifest_validate": "command_center_3_storage_dataset_version_manifest_validate_packet",
        }
        packet_key = storage_packet_keys.get(receipt_key)
        if packet_key:
            try:
                from server.services import storage_service
                from storage.sqlite_meta import SQLiteMetaStore

                receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(packet_key)
                source = "storage_sqlite_packet"
                source_packet_key = packet_key
            except Exception:
                receipt = {}
    if not isinstance(receipt, dict) or not receipt:
        return {}
    status = str(receipt.get("status") or "")
    if not status or status.endswith("_missing"):
        return {}
    return {
        "receipt": dict(receipt),
        "source": source,
        "source_packet_key": source_packet_key,
        "storage_source": storage_source,
        "task_id": str(receipt.get("task_id") or packet_map.get("task_id") or ""),
    }


def _receipt_blocker_count(receipt: dict[str, Any]) -> int:
    blocker_keys = (
        "blocking_row_count",
        "blocking_phase_count",
        "blocking_review_count",
        "local_blocker_count",
        "blocking_criterion_count",
        "production_blocker_count",
        "provider_evidence_blocker_count",
        "credential_missing_provider_count",
        "durable_evidence_blocker_count",
    )
    return max((int(receipt.get(key) or 0) for key in blocker_keys), default=0)


def _receipt_target_payload_safe_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    payload = receipt.get("target_payload_safe") if isinstance(receipt.get("target_payload_safe"), dict) else {}
    payload_map = payload if isinstance(payload, dict) else {}
    target_route = str(receipt.get("target_post_task_route") or receipt.get("target_worker_task_route") or "")
    target_task_type = str(receipt.get("target_task_type") or receipt.get("target_worker_task_type") or "")
    return {
        "target_payload_present": bool(payload_map),
        "target_route": target_route,
        "target_task_type": target_task_type,
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
        "ready_for_manual_physical_task_submission",
        "ready_for_manual_runtime_qa_task_submission",
        "activation_review_ready",
        "evidence_plan_ready",
        "local_recipe_ready",
        "local_receipt_ready",
        "local_review_ready",
        "local_activation_receipt_ready",
        "local_scope_ticket_ready",
        "local_browser_qa_review_ready",
        "local_gate_ready",
        "ci_mirror_ready",
        "push_readiness_receipt_ready",
        "ready_for_explicit_push_sequence",
        "local_schema_seed_ready",
        "schema_seed_ready_for_schema_acceptance",
        "manifest_write_plan_ready",
        "manifest_write_executed",
        "dataset_version_manifest_validated",
    )
    if any(receipt.get(key) is True for key in ready_keys):
        return True
    ready_statuses = {
        "trade_cal_acceptance_dry_run_ready_real_execution_still_blocked",
        "trade_cal_provider_acceptance_promotion_review_recorded_blockers_visible",
        "synthetic_healthcheck_passed_local_task_store_only",
        "backtest_results_schema_seed_ready_for_schema_acceptance",
        "schema_acceptance_evidence_passed_all_local_datasets",
        "schema_acceptance_passed_all_local_datasets",
        "manifest_review_ready_for_manual_write",
        "manifest_write_completed_validated",
        "manifest_validate_passed_local_only",
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
        receipt_lookup_source = "task_payload_safe" if receipt_map else ""
        fallback = {}
        if not receipt_map:
            fallback = _local_receipt_packet_fallback(queue_id, str(step["receipt_key"]))
            fallback_receipt = fallback.get("receipt") if isinstance(fallback.get("receipt"), dict) else {}
            receipt_map = fallback_receipt if isinstance(fallback_receipt, dict) else {}
            if receipt_map:
                receipt_lookup_source = str(fallback.get("source") or "business_packet_fallback")
        if (
            queue_id == "p5_next_session_map_browser_qa"
            and task_type == "run_next_session_browser_qa_review"
            and latest_task.get("status") == "success"
            and str(latest_task.get("current_step") or "") == "next_session_browser_qa_review_ready"
        ):
            receipt_map = {
                "schema_version": "next_session_browser_qa_review.v1",
                "status": "next_session_browser_qa_review_ready_local_artifact",
                "scope": "button_gated_local_next_session_browser_qa_review_no_browser_execution",
                "task_id": str(latest_task.get("task_id") or ""),
                "explicit_review_task_done": True,
                "local_browser_qa_review_ready": True,
                "blocking_review_count": 0,
                "production_replacement_complete": False,
                "streamlit_parity_complete": False,
                "opens_no_browser": True,
                "writes_no_artifacts": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "evidence_boundary": "task_status_derived_local_browser_qa_review_not_browser_execution",
            }
            receipt_lookup_source = "task_status_derived_local_review"
        receipt_scope_hash = str(
            receipt_map.get("acceptance_scope_hash")
            or receipt_map.get("promotion_scope_hash")
            or receipt_map.get("review_scope_hash")
            or receipt_map.get("production_replacement_review_scope_hash")
            or receipt_map.get("physical_execution_scope_hash")
            or receipt_map.get("scope_ticket_sha256")
            or receipt_map.get("runtime_qa_scope_hash")
            or receipt_map.get("benchmark_scope_hash")
            or receipt_map.get("worker_batch_scope_hash")
            or receipt_map.get("scope_hash")
            or ""
        )
        receipt_scope_hash_short = str(
            receipt_map.get("acceptance_scope_hash_short")
            or receipt_map.get("promotion_scope_hash_short")
            or receipt_map.get("review_scope_hash_short")
            or receipt_map.get("production_replacement_review_scope_hash_short")
            or receipt_map.get("physical_execution_scope_hash_short")
            or receipt_map.get("runtime_qa_scope_hash_short")
            or receipt_map.get("benchmark_scope_hash_short")
            or receipt_map.get("worker_batch_scope_hash_short")
            or receipt_map.get("scope_hash_short")
            or (receipt_scope_hash[:16] if receipt_scope_hash else "")
        )
        task_found = bool(latest_task)
        receipt_visible = bool(receipt_map)
        latest_task_storage_source = str(latest_task.get("storage_source") or "") if task_found else ""
        if receipt_visible and receipt_lookup_source != "task_payload_safe" and not latest_task_storage_source:
            latest_task_storage_source = str(fallback.get("storage_source") or "")
        receipt_durable_in_sqlite = bool(
            receipt_visible and latest_task_storage_source in {"memory_and_sqlite", "sqlite_meta", "sqlite_meta_packet"}
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
        local_queue_required = bool(step.get("local_queue_required", True))
        if str(step.get("phase_key") or "").endswith("durable_evidence_recipe"):
            local_queue_required = False
        step_rows.append(
            {
                "phase_key": step["phase_key"],
                "task_type": task_type,
                "route": step["route"],
                "local_queue_required": local_queue_required,
                "task_found": task_found,
                "receipt_visible": receipt_visible,
                "latest_task_id": latest_task.get("task_id") if task_found else fallback.get("task_id", ""),
                "latest_task_status": latest_task.get("status") if task_found else "",
                "latest_task_current_step": latest_task.get("current_step") if task_found else "",
                "latest_task_storage_source": latest_task_storage_source,
                "receipt_lookup_source": receipt_lookup_source,
                "receipt_source_packet_key": fallback.get("source_packet_key", ""),
                "receipt_durable_in_sqlite": receipt_durable_in_sqlite,
                "receipt_memory_only": receipt_memory_only,
                "receipt_durability_state": receipt_durability_state,
                "receipt_durable_required_for_handoff": receipt_visible,
                "receipt_status": receipt_map.get("status") or "",
                "receipt_scope_hash": receipt_scope_hash,
                "receipt_scope_hash_short": receipt_scope_hash_short,
                "receipt_blocker_count": _receipt_blocker_count(receipt_map) if receipt_visible else 0,
                "receipt_target_post_task_route": target_payload_summary.get("target_route") or "",
                "receipt_target_task_type": target_payload_summary.get("target_task_type") or "",
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
                "receipt_ready_for_manual_worker_task_submission": (
                    receipt_map.get("ready_for_manual_worker_task_submission") is True
                ),
                "receipt_ready_for_manual_provider_model_task_submission": (
                    receipt_map.get("ready_for_manual_provider_model_task_submission") is True
                ),
                "receipt_ready_for_manual_physical_task_submission": (
                    receipt_map.get("ready_for_manual_physical_task_submission") is True
                ),
                "receipt_ready_for_manual_runtime_qa_task_submission": (
                    receipt_map.get("ready_for_manual_runtime_qa_task_submission") is True
                ),
                "receipt_creates_provider_task": receipt_map.get("creates_provider_task") is True,
                "receipt_provider_task_created": receipt_map.get("provider_task_created") is True,
                "receipt_provider_execution_implemented": receipt_map.get("provider_execution_implemented") is True,
                "receipt_creates_worker_task": receipt_map.get("creates_worker_task") is True,
                "receipt_worker_task_created": receipt_map.get("worker_task_created") is True,
                "receipt_worker_execution_implemented": receipt_map.get("worker_execution_implemented") is True,
                "receipt_worker_started": receipt_map.get("worker_started") is True,
                "local_ready": local_ready,
                "local_blocked": bool(local_queue_required and receipt_visible and not local_ready),
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
    source_packet_key = "command_center_tushare_refresh_packet"
    try:
        packet = packet_service.read_packet("command_center_tushare_refresh_packet")
    except Exception:
        packet = {}
    recipe = packet.get("provider_target_sample_execution_recipe") if isinstance(packet, dict) else {}
    if not isinstance(recipe, dict) or not recipe:
        source_packet_key = "command_center_tushare_provider_target_sample_execution_recipe_packet"
        try:
            packet = packet_service.read_packet(source_packet_key)
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
        "source_packet_key": source_packet_key,
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


def _latest_candidate_radar_production_replacement_review_preview() -> dict[str, Any]:
    source_packet_key = "command_center_3_candidate_radar_cache"
    try:
        from server.services import candidate_service

        packet = candidate_service.read_candidate_radar_cache()
    except Exception:
        packet = {}
    receipt = packet.get("candidate_radar_production_replacement_review_receipt") if isinstance(packet, dict) else {}
    receipt_map = receipt if isinstance(receipt, dict) else {}
    status = str(receipt_map.get("status") or "")
    review_scope_hash = str(receipt_map.get("review_scope_hash") or "")
    review_scope_hash_short = str(receipt_map.get("review_scope_hash_short") or review_scope_hash[:16])
    review_visible = bool(receipt_map and status and not status.endswith("_missing"))
    review_ready = bool(
        review_visible
        and receipt_map.get("local_review_ready") is True
        and receipt_map.get("production_radar_replacement_complete") is False
        and receipt_map.get("legacy_retirement_ready") is False
        and receipt_map.get("external_calls_triggered") is False
        and receipt_map.get("tushare_called") is False
        and receipt_map.get("deepseek_called") is False
        and receipt_map.get("github_called") is False
        and receipt_map.get("does_not_execute_trades") is True
        and receipt_map.get("does_not_modify_strategy_action") is True
        and receipt_map.get("contains_secret") is False
        and bool(review_scope_hash)
    )
    return {
        "review_visible": review_visible,
        "review_status": status,
        "review_scope_hash": review_scope_hash,
        "review_scope_hash_short": review_scope_hash_short,
        "review_local_ready": receipt_map.get("local_review_ready") is True,
        "can_prebind_review_scope_hash": review_ready,
        "source_packet_key": source_packet_key,
        "source_receipt_key": "candidate_radar_production_replacement_review_receipt",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_boundary": "latest_candidate_radar_replacement_review_preview_is_read_only_not_promotion",
    }


def _latest_storage_physical_execution_recipe_preview() -> dict[str, Any]:
    try:
        from server.services import storage_service

        packet = storage_service.storage_overview()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    recipe = packet_map.get("storage_physical_execution_recipe")
    recipe_map = recipe if isinstance(recipe, dict) else {}
    scope_hash = str(recipe_map.get("physical_execution_scope_hash") or "")
    scope_hash_short = str(recipe_map.get("physical_execution_scope_hash_short") or scope_hash[:12])
    recipe_ready = bool(
        recipe_map.get("local_recipe_ready") is True
        and recipe_map.get("production_storage_complete") is False
        and recipe_map.get("external_calls_triggered") is False
        and recipe_map.get("tushare_called") is False
        and recipe_map.get("deepseek_called") is False
        and recipe_map.get("github_called") is False
        and recipe_map.get("does_not_execute_trades") is True
        and recipe_map.get("does_not_modify_strategy_action") is True
        and recipe_map.get("contains_secret") is False
        and bool(scope_hash)
    )
    return {
        "recipe_visible": bool(recipe_map),
        "recipe_status": str(recipe_map.get("status") or ""),
        "physical_execution_scope_hash": scope_hash,
        "physical_execution_scope_hash_short": scope_hash_short,
        "can_prebind_physical_execution_scope_hash": recipe_ready,
        "source_packet_key": "command_center_3_storage_overview",
        "source_receipt_key": "storage_physical_execution_recipe",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_boundary": "latest_storage_physical_execution_recipe_preview_is_read_only_not_execution",
    }


def _latest_storage_direct_execution_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import storage_service
        from storage.sqlite_meta import SQLiteMetaStore

        schema_evidence = storage_service.storage_schema_validation_acceptance_evidence_audit()
        schema_migration_execution = storage_service.storage_schema_migration_execution_evidence()
        execution_request = storage_service.storage_physical_execution_request_evidence()
        duckdb_read_validation = storage_service.storage_duckdb_read_validation_evidence()
        try:
            manifest_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY
            )
        except Exception:
            manifest_packet = {}
        try:
            partition_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.PARTITION_MIGRATION_DRY_RUN_PACKET_KEY
            )
        except Exception:
            partition_packet = {}
        try:
            compaction_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.COMPACTION_DRY_RUN_PACKET_KEY
            )
        except Exception:
            compaction_packet = {}
        try:
            cleanup_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY
            )
        except Exception:
            cleanup_packet = {}
        try:
            cache_ttl_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.CACHE_TTL_DRY_RUN_PACKET_KEY
            )
        except Exception:
            cache_ttl_packet = {}
    except Exception:
        return {
            "schema_version": "migration_storage_direct_execution_evidence_summary.v1",
            "source_packet_key": "storage_sqlite_packets",
            "available": False,
            "status": "storage_direct_evidence_read_failed_safe_fallback",
            "direct_evidence_stage_count": 0,
            "physical_schema_validation_done": False,
            "schema_migration_executed": False,
            "dataset_version_manifest_validated": False,
            "duckdb_read_validation_done": False,
            "partition_migration_metadata_validation_done": False,
            "physical_compaction_metadata_validation_done": False,
            "cache_ttl_refresh_metadata_validation_done": False,
            "artifact_cleanup_review_done": False,
            "storage_physical_execution_request_ready": False,
            "production_storage_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "direct_evidence_layer": "L1_static_contract",
        }

    schema_map = schema_evidence if isinstance(schema_evidence, dict) else {}
    schema_migration_map = schema_migration_execution if isinstance(schema_migration_execution, dict) else {}
    manifest_map = manifest_packet if isinstance(manifest_packet, dict) else {}
    partition_map = partition_packet if isinstance(partition_packet, dict) else {}
    compaction_map = compaction_packet if isinstance(compaction_packet, dict) else {}
    cleanup_map = cleanup_packet if isinstance(cleanup_packet, dict) else {}
    cache_ttl_map = cache_ttl_packet if isinstance(cache_ttl_packet, dict) else {}
    cleanup_review_map = (
        cleanup_map.get("artifact_cleanup_review_contract")
        if isinstance(cleanup_map.get("artifact_cleanup_review_contract"), dict)
        else {}
    )
    request_map = execution_request if isinstance(execution_request, dict) else {}
    duckdb_map = duckdb_read_validation if isinstance(duckdb_read_validation, dict) else {}
    schema_done = bool(
        schema_map.get("physical_schema_validation_done") is True
        and schema_map.get("status") == "schema_acceptance_evidence_passed_all_local_datasets"
        and schema_map.get("external_calls_triggered") is False
        and schema_map.get("tushare_called") is False
        and schema_map.get("deepseek_called") is False
        and schema_map.get("github_called") is False
        and schema_map.get("does_not_execute_trades") is True
        and schema_map.get("production_storage_complete") is False
    )
    manifest_done = bool(
        manifest_map.get("schema_version") == "command_center_3_storage_dataset_version_manifest_validate.v1"
        and manifest_map.get("status") == "manifest_validate_passed_local_only"
        and manifest_map.get("dataset_version_manifest_validated") is True
        and manifest_map.get("external_calls_triggered") is False
        and manifest_map.get("tushare_called") is False
        and manifest_map.get("deepseek_called") is False
        and manifest_map.get("github_called") is False
        and manifest_map.get("does_not_execute_trades") is True
        and manifest_map.get("production_storage_complete") is False
    )
    schema_migration_done = bool(
        schema_migration_map.get("schema_version") == "command_center_3_storage_schema_migration_execution.v1"
        and schema_migration_map.get("status") == "schema_migration_execution_completed_noop_verified"
        and schema_migration_map.get("schema_migration_executed") is True
        and schema_migration_map.get("schema_migration_noop_verified") is True
        and schema_migration_map.get("schema_migration_rewrite_executed") is False
        and int(schema_migration_map.get("dataset_count") or 0) > 0
        and int(schema_migration_map.get("schema_migration_executed_count") or 0)
        == int(schema_migration_map.get("dataset_count") or 0)
        and int(schema_migration_map.get("schema_migration_noop_verified_count") or 0)
        == int(schema_migration_map.get("dataset_count") or 0)
        and schema_migration_map.get("physical_schema_validation_done") is True
        and schema_migration_map.get("dataset_version_manifest_validated") is True
        and schema_migration_map.get("post_task_writes_parquet") is False
        and schema_migration_map.get("post_task_writes_manifest") is False
        and schema_migration_map.get("post_task_reads_row_payloads") is False
        and schema_migration_map.get("cache_get_writes_files") is False
        and schema_migration_map.get("production_storage_complete") is False
        and schema_migration_map.get("external_calls_triggered") is False
        and schema_migration_map.get("tushare_called") is False
        and schema_migration_map.get("deepseek_called") is False
        and schema_migration_map.get("github_called") is False
        and schema_migration_map.get("does_not_execute_trades") is True
        and schema_migration_map.get("does_not_modify_strategy_action") is True
        and schema_migration_map.get("contains_secret") is False
    )
    request_ready = bool(
        request_map.get("local_execution_request_ready") is True
        and request_map.get("external_calls_triggered") is False
        and request_map.get("tushare_called") is False
        and request_map.get("deepseek_called") is False
        and request_map.get("github_called") is False
        and request_map.get("does_not_execute_trades") is True
        and request_map.get("production_storage_complete") is False
    )
    duckdb_read_validation_done = bool(
        duckdb_map.get("schema_version") == "command_center_3_storage_duckdb_read_validation.v1"
        and duckdb_map.get("status") == "storage_duckdb_read_validation_ready_local_query_contract"
        and duckdb_map.get("local_duckdb_read_validation_ready") is True
        and duckdb_map.get("duckdb_dependency_available") is True
        and int(duckdb_map.get("dataset_count") or 0) > 0
        and int(duckdb_map.get("contract_ready_count") or 0) == int(duckdb_map.get("dataset_count") or 0)
        and duckdb_map.get("query_result_contract_schema_version") == "duckdb_query_result_contract.v1"
        and duckdb_map.get("query_wrapper") == "duckdb_filtered_parquet.v1"
        and duckdb_map.get("safe_parameter_binding") is True
        and duckdb_map.get("typed_projection_enabled") is True
        and duckdb_map.get("cursor_pagination_enabled") is True
        and duckdb_map.get("frontend_executes_query") is False
        and duckdb_map.get("cache_get_writes_files") is False
        and duckdb_map.get("writes_parquet_on_get") is False
        and duckdb_map.get("writes_parquet") is False
        and duckdb_map.get("writes_manifest") is False
        and duckdb_map.get("deletes_artifacts") is False
        and duckdb_map.get("refreshes_providers") is False
        and duckdb_map.get("schema_migration_executed") is False
        and duckdb_map.get("partition_migration_executed") is False
        and duckdb_map.get("physical_compaction_executed") is False
        and duckdb_map.get("cache_ttl_refresh_executed") is False
        and duckdb_map.get("artifact_cleanup_delete_executed") is False
        and duckdb_map.get("post_migration_validation_done") is False
        and duckdb_map.get("production_storage_complete") is False
        and duckdb_map.get("external_calls_triggered") is False
        and duckdb_map.get("tushare_called") is False
        and duckdb_map.get("deepseek_called") is False
        and duckdb_map.get("github_called") is False
        and duckdb_map.get("does_not_execute_trades") is True
        and duckdb_map.get("does_not_modify_strategy_action") is True
        and duckdb_map.get("contains_secret") is False
    )
    partition_metadata_validation_done = bool(
        partition_map.get("schema_version") == "command_center_3_storage_partition_migration_dry_run.v1"
        and partition_map.get("status") == "dry_run_completed"
        and partition_map.get("partition_migration_metadata_validation_done") is True
        and int(partition_map.get("dataset_count") or 0) > 0
        and int(partition_map.get("partition_migration_metadata_validated_count") or 0)
        == int(partition_map.get("dataset_count") or 0)
        and int(partition_map.get("partition_migration_blocked_count") or 0) == 0
        and partition_map.get("partition_migration_executed") is False
        and int(partition_map.get("partition_migration_executed_count") or 0) == 0
        and partition_map.get("post_dry_run_writes_parquet") is False
        and partition_map.get("post_dry_run_reads_row_payloads") is False
        and partition_map.get("post_dry_run_reads_env_files") is False
        and partition_map.get("cache_get_writes_files") is False
        and partition_map.get("production_storage_complete") is False
        and partition_map.get("external_calls_triggered") is False
        and partition_map.get("tushare_called") is False
        and partition_map.get("deepseek_called") is False
        and partition_map.get("github_called") is False
        and partition_map.get("does_not_execute_trades") is True
        and partition_map.get("does_not_modify_strategy_action") is True
        and partition_map.get("contains_secret") is False
    )
    physical_compaction_metadata_validation_done = bool(
        compaction_map.get("schema_version") == "command_center_3_storage_compaction_dry_run.v1"
        and compaction_map.get("status") == "dry_run_completed"
        and compaction_map.get("physical_compaction_metadata_validation_done") is True
        and int(compaction_map.get("dataset_count") or 0) > 0
        and int(compaction_map.get("physical_compaction_metadata_validated_count") or 0)
        == int(compaction_map.get("dataset_count") or 0)
        and int(compaction_map.get("compaction_not_needed_count") or 0)
        == int(compaction_map.get("dataset_count") or 0)
        and int(compaction_map.get("compaction_ready_count") or 0) == 0
        and int(compaction_map.get("compaction_blocked_count") or 0) == 0
        and int(compaction_map.get("missing_dataset_count") or 0) == 0
        and compaction_map.get("compaction_executed") is False
        and compaction_map.get("physical_compaction_executed") is False
        and int(compaction_map.get("compaction_executed_count") or 0) == 0
        and compaction_map.get("post_dry_run_writes_parquet") is False
        and compaction_map.get("post_dry_run_reads_row_payloads") is False
        and compaction_map.get("post_dry_run_reads_env_files") is False
        and compaction_map.get("cache_get_writes_files") is False
        and compaction_map.get("production_storage_complete") is False
        and compaction_map.get("external_calls_triggered") is False
        and compaction_map.get("tushare_called") is False
        and compaction_map.get("deepseek_called") is False
        and compaction_map.get("github_called") is False
        and compaction_map.get("does_not_execute_trades") is True
        and compaction_map.get("does_not_modify_strategy_action") is True
        and compaction_map.get("contains_secret") is False
    )
    cache_ttl_refresh_metadata_validation_done = bool(
        cache_ttl_map.get("schema_version") == "command_center_3_storage_cache_ttl_dry_run.v1"
        and cache_ttl_map.get("status") == "dry_run_completed"
        and int(cache_ttl_map.get("dataset_count") or 0) > 0
        and int(cache_ttl_map.get("refresh_executed_count") or 0) == 0
        and cache_ttl_map.get("refresh_executed") is False
        and cache_ttl_map.get("auto_refresh_on_get") is False
        and cache_ttl_map.get("post_dry_run_writes_parquet") is False
        and cache_ttl_map.get("post_dry_run_reads_row_payloads") is False
        and cache_ttl_map.get("post_dry_run_reads_env_files") is False
        and cache_ttl_map.get("cache_get_writes_files") is False
        and cache_ttl_map.get("external_calls_triggered") is False
        and cache_ttl_map.get("tushare_called") is False
        and cache_ttl_map.get("deepseek_called") is False
        and cache_ttl_map.get("github_called") is False
        and cache_ttl_map.get("does_not_execute_trades") is True
        and cache_ttl_map.get("does_not_modify_strategy_action") is True
        and cache_ttl_map.get("contains_secret") is False
    )
    artifact_cleanup_review_done = bool(
        cleanup_map.get("schema_version") == "command_center_3_storage_artifact_cleanup_dry_run.v1"
        and cleanup_map.get("status") == "ready"
        and cleanup_map.get("artifact_cleanup_review_done") is True
        and str(cleanup_map.get("artifact_cleanup_review_status") or "").startswith("manual_review_ready")
        and int(cleanup_map.get("candidate_count") or 0) >= 0
        and int(cleanup_map.get("present_artifact_count") or 0) >= 0
        and int(cleanup_map.get("artifact_cleanup_review_required_step_count") or 0) > 0
        and cleanup_map.get("manual_approval_required_before_delete") is True
        and cleanup_map.get("delete_execution_task_available") is False
        and int(cleanup_map.get("delete_executed_count") or 0) == 0
        and cleanup_map.get("safe_delete_command_generated") is False
        and cleanup_map.get("cleanup_review_is_not_delete_execution") is True
        and cleanup_map.get("production_cleanup_complete") is False
        and cleanup_map.get("delete_files_on_post") is False
        and cleanup_map.get("auto_cleanup_on_post") is False
        and cleanup_map.get("would_delete_files") is False
        and cleanup_map.get("does_not_scan_secret_values") is True
        and cleanup_map.get("does_not_read_file_payloads") is True
        and cleanup_map.get("does_not_read_env_files") is True
        and cleanup_map.get("external_calls_triggered") is False
        and cleanup_map.get("tushare_called") is False
        and cleanup_map.get("deepseek_called") is False
        and cleanup_map.get("github_called") is False
        and cleanup_map.get("does_not_execute_trades") is True
        and cleanup_map.get("does_not_modify_strategy_action") is True
        and cleanup_map.get("contains_secret") is False
        and cleanup_review_map.get("artifact_cleanup_review_done") is True
        and cleanup_review_map.get("delete_executed") is False
        and cleanup_review_map.get("cleanup_review_is_not_delete_execution") is True
        and cleanup_review_map.get("production_cleanup_complete") is False
        and cleanup_review_map.get("contains_secret") is False
    )
    direct_evidence_count = (
        int(schema_done)
        + int(schema_migration_done)
        + int(manifest_done)
        + int(duckdb_read_validation_done)
        + int(partition_metadata_validation_done)
        + int(physical_compaction_metadata_validation_done)
        + int(cache_ttl_refresh_metadata_validation_done)
        + int(artifact_cleanup_review_done)
    )
    try:
        schema_done_count = int(schema_map.get("physical_schema_validation_done_count") or 0)
    except Exception:
        schema_done_count = 0
    try:
        manifest_validated_count = int(
            manifest_map.get("validated_dataset_count")
            or manifest_map.get("physical_dataset_version_validated_count")
            or 0
        )
    except Exception:
        manifest_validated_count = 0
    return {
        "schema_version": "migration_storage_direct_execution_evidence_summary.v1",
        "source_packet_key": "storage_sqlite_packets",
        "source_schema_acceptance_packet_key": getattr(
            storage_service,
            "SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY",
            "command_center_3_storage_schema_validation_acceptance_packet",
        ),
        "source_schema_migration_execution_packet_key": getattr(
            storage_service,
            "SCHEMA_MIGRATION_EXECUTION_PACKET_KEY",
            "command_center_3_storage_schema_migration_execution_packet",
        ),
        "source_manifest_validate_packet_key": getattr(
            storage_service,
            "DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY",
            "command_center_3_storage_dataset_version_manifest_validate_packet",
        ),
        "source_physical_execution_request_packet_key": getattr(
            storage_service,
            "STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY",
            "command_center_3_storage_physical_execution_request_packet",
        ),
        "available": bool(direct_evidence_count),
        "status": "storage_direct_evidence_visible_production_pending"
        if direct_evidence_count
        else "storage_direct_evidence_missing",
        "direct_evidence_stage_count": direct_evidence_count,
        "physical_schema_validation_done": schema_done,
        "physical_schema_validation_done_count": schema_done_count,
        "schema_validation_acceptance_evidence_status": str(schema_map.get("status") or ""),
        "schema_migration_executed": schema_migration_done,
        "schema_migration_execution_status": str(schema_migration_map.get("status") or "packet_missing"),
        "schema_migration_executed_count": int(schema_migration_map.get("schema_migration_executed_count") or 0),
        "schema_migration_dataset_count": int(schema_migration_map.get("dataset_count") or 0),
        "schema_migration_noop_verified_count": int(
            schema_migration_map.get("schema_migration_noop_verified_count") or 0
        ),
        "schema_migration_rewrite_executed": schema_migration_map.get("schema_migration_rewrite_executed") is True,
        "dataset_version_manifest_validated": manifest_done,
        "dataset_version_manifest_validate_packet_status": str(manifest_map.get("status") or "packet_missing"),
        "dataset_version_manifest_validated_count": manifest_validated_count,
        "manifest_exists": bool(manifest_map.get("manifest_exists")),
        "duckdb_read_validation_done": duckdb_read_validation_done,
        "duckdb_read_validation_status": str(duckdb_map.get("status") or "packet_missing"),
        "duckdb_read_validation_dataset_count": int(duckdb_map.get("dataset_count") or 0),
        "duckdb_read_validation_contract_ready_count": int(duckdb_map.get("contract_ready_count") or 0),
        "duckdb_read_validation_ready_dataset_count": int(duckdb_map.get("ready_dataset_count") or 0),
        "partition_migration_metadata_validation_done": partition_metadata_validation_done,
        "partition_migration_metadata_validation_status": str(partition_map.get("status") or "packet_missing"),
        "partition_migration_metadata_validated_count": int(
            partition_map.get("partition_migration_metadata_validated_count") or 0
        ),
        "partition_migration_dataset_count": int(partition_map.get("dataset_count") or 0),
        "physical_compaction_metadata_validation_done": physical_compaction_metadata_validation_done,
        "physical_compaction_metadata_validation_status": str(compaction_map.get("status") or "packet_missing"),
        "physical_compaction_metadata_validated_count": int(
            compaction_map.get("physical_compaction_metadata_validated_count") or 0
        ),
        "physical_compaction_dataset_count": int(compaction_map.get("dataset_count") or 0),
        "physical_compaction_not_needed_count": int(compaction_map.get("compaction_not_needed_count") or 0),
        "cache_ttl_refresh_metadata_validation_done": cache_ttl_refresh_metadata_validation_done,
        "cache_ttl_refresh_metadata_validation_status": str(cache_ttl_map.get("status") or "packet_missing"),
        "cache_ttl_refresh_recommended_count": int(cache_ttl_map.get("refresh_recommended_count") or 0),
        "cache_ttl_dataset_count": int(cache_ttl_map.get("dataset_count") or 0),
        "cache_ttl_refresh_executed_count": int(cache_ttl_map.get("refresh_executed_count") or 0),
        "artifact_cleanup_review_done": artifact_cleanup_review_done,
        "artifact_cleanup_review_status": str(cleanup_map.get("artifact_cleanup_review_status") or "packet_missing"),
        "artifact_cleanup_candidate_count": int(cleanup_map.get("candidate_count") or 0),
        "artifact_cleanup_review_required_step_count": int(
            cleanup_map.get("artifact_cleanup_review_required_step_count") or 0
        ),
        "storage_physical_execution_request_ready": request_ready,
        "storage_physical_execution_request_status": str(request_map.get("status") or "packet_missing"),
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_storage_physical_execution_evidence"
        if direct_evidence_count
        else "L1_static_contract",
        "evidence_boundary": "storage_schema_manifest_direct_evidence_is_not_production_storage_completion",
    }


def _latest_worker_runtime_qa_context_preview() -> dict[str, Any]:
    try:
        from server.services import worker_service

        packet = worker_service.read_worker_runtime_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    plan = packet_map.get("worker_production_evidence_plan_receipt")
    recipe = packet_map.get("worker_runtime_qa_execution_recipe")
    request = packet_map.get("worker_runtime_qa_execution_request_receipt")
    plan_map = plan if isinstance(plan, dict) else {}
    recipe_map = recipe if isinstance(recipe, dict) else {}
    request_map = request if isinstance(request, dict) else {}
    plan_scope_hash = str(plan_map.get("scope_ticket_sha256") or "")
    recipe_scope_hash = str(recipe_map.get("runtime_qa_scope_hash") or "")
    request_task_id = str(request_map.get("request_task_id") or "")
    request_evidence_plan_scope_hash = str(request_map.get("production_evidence_plan_scope_hash") or plan_scope_hash)
    request_runtime_scope_hash = str(request_map.get("runtime_qa_scope_hash") or recipe_scope_hash)
    plan_ready = plan_map.get("evidence_plan_ready") is True
    recipe_ready = recipe_map.get("local_recipe_ready") is True
    request_ready = request_map.get("local_execution_request_ready") is True
    no_side_effects = bool(
        packet_map.get("external_calls_triggered") is not True
        and packet_map.get("tushare_called") is not True
        and packet_map.get("deepseek_called") is not True
        and packet_map.get("github_called") is not True
        and packet_map.get("does_not_execute_trades") is True
        and packet_map.get("does_not_modify_strategy_action") is True
        and packet_map.get("contains_secret") is not True
    )
    return {
        "evidence_plan_visible": bool(plan_map),
        "evidence_plan_status": str(plan_map.get("status") or ""),
        "evidence_plan_scope_hash": plan_scope_hash,
        "evidence_plan_scope_hash_short": plan_scope_hash[:12],
        "runtime_qa_recipe_visible": bool(recipe_map),
        "runtime_qa_recipe_status": str(recipe_map.get("status") or ""),
        "runtime_qa_scope_hash": recipe_scope_hash,
        "runtime_qa_scope_hash_short": recipe_scope_hash[:12],
        "runtime_qa_request_visible": bool(request_map),
        "runtime_qa_request_status": str(request_map.get("status") or ""),
        "runtime_qa_request_task_id": request_task_id,
        "runtime_qa_request_evidence_plan_scope_hash": request_evidence_plan_scope_hash,
        "runtime_qa_request_runtime_scope_hash": request_runtime_scope_hash,
        "can_prebind_runtime_qa_execution_request_scope": bool(plan_ready and recipe_ready and no_side_effects),
        "can_prebind_runtime_qa_dry_run_scope": bool(
            request_ready and bool(request_task_id) and bool(request_evidence_plan_scope_hash) and bool(request_runtime_scope_hash)
        ),
        "source_packet_key": "command_center_3_worker_runtime_cache",
        "source_receipt_key": "worker_runtime_qa_execution_recipe",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_boundary": "latest_worker_runtime_qa_context_preview_is_read_only_not_execution",
    }


def _latest_worker_direct_runtime_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import worker_service

        packet = worker_service.read_worker_runtime_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    synthetic = packet_map.get("worker_synthetic_healthcheck")
    runtime_request = packet_map.get("worker_runtime_qa_execution_request_receipt")
    runtime_dry_run = packet_map.get("worker_runtime_qa_dry_run_receipt")
    runtime_execution = packet_map.get("worker_runtime_qa_execution_receipt")
    synthetic_map = synthetic if isinstance(synthetic, dict) else {}
    request_map = runtime_request if isinstance(runtime_request, dict) else {}
    dry_run_map = runtime_dry_run if isinstance(runtime_dry_run, dict) else {}
    execution_map = runtime_execution if isinstance(runtime_execution, dict) else {}
    synthetic_done = bool(
        synthetic_map.get("schema_version") == "worker_synthetic_healthcheck.v1"
        and synthetic_map.get("status") == "synthetic_healthcheck_passed_local_task_store_only"
        and synthetic_map.get("synthetic_healthcheck_executed") is True
        and synthetic_map.get("local_task_round_trip_verified") is True
        and synthetic_map.get("task_log_round_trip_verified") is True
        and synthetic_map.get("task_readback_hash_matches") is True
        and synthetic_map.get("source_packet_present") is True
        and synthetic_map.get("celery_worker_started") is False
        and synthetic_map.get("redis_pinged") is False
        and synthetic_map.get("scheduler_started") is False
        and synthetic_map.get("production_worker_complete") is False
        and synthetic_map.get("external_calls_triggered") is False
        and synthetic_map.get("tushare_called") is False
        and synthetic_map.get("deepseek_called") is False
        and synthetic_map.get("github_called") is False
        and synthetic_map.get("does_not_execute_trades") is True
        and synthetic_map.get("does_not_modify_strategy_action") is True
        and synthetic_map.get("contains_secret") is False
    )
    runtime_request_ready = bool(
        request_map.get("schema_version") == "worker_runtime_qa_execution_request_receipt.v1"
        and request_map.get("status") == "worker_runtime_qa_execution_request_ready_manual_runtime_qa_pending"
        and request_map.get("local_execution_request_ready") is True
        and request_map.get("runtime_qa_task_created") is False
        and request_map.get("runtime_qa_task_executed") is False
        and request_map.get("production_worker_complete") is False
        and request_map.get("worker_started") is False
        and request_map.get("redis_pinged") is False
        and request_map.get("scheduler_started") is False
        and request_map.get("task_dispatched") is False
        and request_map.get("provider_model_task_dispatched") is False
        and request_map.get("external_calls_triggered") is False
        and request_map.get("tushare_called") is False
        and request_map.get("deepseek_called") is False
        and request_map.get("github_called") is False
        and request_map.get("does_not_execute_trades") is True
        and request_map.get("does_not_modify_strategy_action") is True
        and request_map.get("contains_secret") is False
    )
    runtime_dry_run_ready = bool(
        dry_run_map.get("schema_version") == "worker_runtime_qa_dry_run_receipt.v1"
        and dry_run_map.get("status") == "worker_runtime_qa_dry_run_ready_execution_pending"
        and dry_run_map.get("local_dry_run_ready") is True
        and dry_run_map.get("runtime_qa_task_created") is False
        and dry_run_map.get("runtime_qa_task_executed") is False
        and dry_run_map.get("production_worker_complete") is False
        and dry_run_map.get("worker_started") is False
        and dry_run_map.get("redis_pinged") is False
        and dry_run_map.get("scheduler_started") is False
        and dry_run_map.get("task_dispatched") is False
        and dry_run_map.get("provider_model_task_dispatched") is False
        and dry_run_map.get("external_calls_triggered") is False
        and dry_run_map.get("tushare_called") is False
        and dry_run_map.get("deepseek_called") is False
        and dry_run_map.get("github_called") is False
        and dry_run_map.get("does_not_execute_trades") is True
        and dry_run_map.get("does_not_modify_strategy_action") is True
        and dry_run_map.get("contains_secret") is False
    )
    provider_boundary_done = bool(synthetic_done and runtime_request_ready and runtime_dry_run_ready)
    no_trade_no_action_done = bool(
        provider_boundary_done
        and packet_map.get("does_not_execute_trades") is True
        and packet_map.get("does_not_modify_strategy_action") is True
    )
    scheduler_default_off_done = bool(
        synthetic_done
        and runtime_request_ready
        and runtime_dry_run_ready
        and synthetic_map.get("scheduler_started") is False
        and request_map.get("scheduler_started") is False
        and dry_run_map.get("scheduler_started") is False
    )
    runtime_execution_done = bool(
        execution_map.get("schema_version") == "worker_runtime_qa_execution_receipt.v1"
        and execution_map.get("status") == "worker_runtime_qa_execution_ready_local_fallback_evidence"
        and execution_map.get("local_runtime_qa_execution_done") is True
        and execution_map.get("runtime_qa_task_created") is True
        and execution_map.get("runtime_qa_task_executed") is True
        and execution_map.get("runtime_qa_execution_implemented") is True
        and execution_map.get("local_fallback_round_trip_verified") is True
        and execution_map.get("local_task_round_trip_verified") is True
        and execution_map.get("task_log_round_trip_verified") is True
        and execution_map.get("task_log_persistence_verified") is True
        and execution_map.get("append_only_worker_log_verified") is True
        and execution_map.get("scheduler_default_off_runtime_verified") is True
        and execution_map.get("provider_model_no_autoschedule_boundary_verified") is True
        and execution_map.get("no_trade_no_action_boundary_verified") is True
        and execution_map.get("production_worker_complete") is False
        and execution_map.get("worker_started") is False
        and execution_map.get("celery_worker_started") is False
        and execution_map.get("redis_pinged") is False
        and execution_map.get("scheduler_started") is False
        and execution_map.get("task_dispatched") is False
        and execution_map.get("provider_model_task_dispatched") is False
        and execution_map.get("external_calls_triggered") is False
        and execution_map.get("tushare_called") is False
        and execution_map.get("deepseek_called") is False
        and execution_map.get("github_called") is False
        and execution_map.get("does_not_execute_trades") is True
        and execution_map.get("does_not_modify_strategy_action") is True
        and execution_map.get("contains_secret") is False
    )
    cross_process_task_control_done = bool(
        runtime_execution_done
        and execution_map.get("cross_process_task_control_verified") is True
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("status")
        == "cross_process_task_control_verified"
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("readback_hash_matches") is True
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("external_calls_triggered")
        is False
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("tushare_called") is False
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("deepseek_called") is False
        and _dict_or_empty(execution_map.get("cross_process_task_control_probe")).get("github_called") is False
    )
    direct_stage_keys = []
    if cross_process_task_control_done:
        direct_stage_keys.append("cross_process_retry_cancel_lock_dedupe")
    if runtime_execution_done:
        direct_stage_keys.append("append_only_worker_logs")
    if scheduler_default_off_done:
        direct_stage_keys.append("scheduler_default_off_runtime")
    if provider_boundary_done:
        direct_stage_keys.append("provider_model_no_autoschedule_boundary")
    if no_trade_no_action_done:
        direct_stage_keys.append("no_trade_no_action_boundary")
    return {
        "schema_version": "migration_worker_direct_runtime_evidence_summary.v1",
        "source_packet_key": "command_center_3_worker_runtime_cache",
        "status": "worker_direct_runtime_evidence_visible_production_pending"
        if direct_stage_keys
        else "worker_direct_runtime_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "synthetic_healthcheck_executed": synthetic_done,
        "local_task_round_trip_verified": synthetic_map.get("local_task_round_trip_verified") is True,
        "task_log_round_trip_verified": synthetic_map.get("task_log_round_trip_verified") is True,
        "task_readback_hash_matches": synthetic_map.get("task_readback_hash_matches") is True,
        "runtime_qa_execution_request_ready": runtime_request_ready,
        "runtime_qa_dry_run_ready": runtime_dry_run_ready,
        "runtime_qa_execution_done": runtime_execution_done,
        "local_fallback_round_trip_verified": execution_map.get("local_fallback_round_trip_verified") is True,
        "task_log_persistence_verified": execution_map.get("task_log_persistence_verified") is True,
        "local_task_control_metadata_verified": execution_map.get("local_task_control_metadata_verified") is True,
        "cross_process_task_control_verified": cross_process_task_control_done,
        "append_only_worker_log_verified": execution_map.get("append_only_worker_log_verified") is True,
        "scheduler_default_off_runtime_verified": scheduler_default_off_done,
        "provider_model_no_autoschedule_boundary_verified": provider_boundary_done,
        "no_trade_no_action_boundary_verified": no_trade_no_action_done,
        "synthetic_healthcheck_status": str(synthetic_map.get("status") or "packet_missing"),
        "runtime_qa_execution_request_status": str(request_map.get("status") or "packet_missing"),
        "runtime_qa_dry_run_status": str(dry_run_map.get("status") or "packet_missing"),
        "runtime_qa_execution_status": str(execution_map.get("status") or "packet_missing"),
        "production_worker_complete": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_worker_runtime_execution_evidence"
        if runtime_execution_done
        else "L3_local_worker_runtime_safety_evidence"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "worker_synthetic_runtime_qa_direct_evidence_is_not_production_worker_completion",
    }


def _latest_next_session_direct_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import next_session_service

        packet = next_session_service.read_next_session_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    browser_evidence = _dict_or_empty(packet_map.get("next_session_browser_qa_evidence_summary"))
    browser_review = _dict_or_empty(packet_map.get("next_session_browser_qa_review_contract"))
    packet_safe = bool(
        packet_map.get("external_calls_triggered") is not True
        and packet_map.get("tushare_called") is not True
        and packet_map.get("deepseek_called") is not True
        and packet_map.get("github_called") is not True
        and packet_map.get("does_not_execute_trades") is not False
        and packet_map.get("does_not_modify_strategy_action") is not False
    )
    review_ready = bool(
        browser_review.get("schema_version") == "next_session_browser_qa_review.v1"
        and browser_review.get("status") == "next_session_browser_qa_review_ready_local_artifact"
        and browser_review.get("explicit_review_task_done") is True
        and browser_review.get("local_browser_qa_review_ready") is True
        and int(browser_review.get("blocking_review_count") or 0) == 0
        and browser_review.get("streamlit_parity_complete") is False
        and browser_review.get("production_replacement_complete") is False
        and browser_review.get("opens_no_browser") is True
        and browser_review.get("starts_no_servers") is True
        and browser_review.get("writes_no_artifacts") is True
        and browser_review.get("external_calls_triggered") is False
        and browser_review.get("tushare_called") is False
        and browser_review.get("deepseek_called") is False
        and browser_review.get("github_called") is False
        and browser_review.get("does_not_execute_trades") is True
        and browser_review.get("does_not_modify_strategy_action") is True
        and browser_review.get("does_not_modify_operation_zones") is True
    )
    visual_done = bool(
        packet_safe
        and review_ready
        and browser_evidence.get("next_visual_qa_evidence_passed") is True
        and browser_review.get("next_visual_qa_evidence_passed") is True
    )
    performance_done = bool(
        packet_safe
        and review_ready
        and browser_evidence.get("next_browser_performance_evidence_passed") is True
        and browser_review.get("next_browser_performance_evidence_passed") is True
    )
    reduced_motion_done = bool(
        packet_safe
        and review_ready
        and browser_evidence.get("default_motion_passed") is True
        and browser_evidence.get("reduced_motion_passed") is True
        and browser_review.get("default_motion_passed") is True
        and browser_review.get("reduced_motion_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
    )
    direct_stage_keys = []
    if visual_done:
        direct_stage_keys.append("browser_visual_qa")
    if performance_done:
        direct_stage_keys.append("browser_performance_trace")
    if reduced_motion_done:
        direct_stage_keys.append("reduced_motion_accessibility_qa")
    return {
        "schema_version": "migration_next_session_direct_evidence_summary.v1",
        "source_packet_key": "command_center_next_session_projection_packet + command_center_next_session_browser_qa_review_packet",
        "status": "next_session_direct_browser_evidence_visible_production_pending"
        if direct_stage_keys
        else "next_session_direct_browser_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "browser_visual_qa_done": visual_done,
        "browser_performance_trace_done": performance_done,
        "reduced_motion_accessibility_qa_done": reduced_motion_done,
        "local_browser_qa_review_ready": review_ready,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_next_session_browser_visual_performance_evidence"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "next_session_browser_qa_review_is_not_streamlit_parity_or_production_replacement",
    }


def _latest_tauri_package_direct_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import desktop_service

        packet = desktop_service.read_desktop_shell_preflight_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    review = _dict_or_empty(packet_map.get("tauri_package_artifact_review_contract"))
    launch_review = _dict_or_empty(packet_map.get("tauri_packaged_runtime_launch_review_contract"))
    offline_ux_review = _dict_or_empty(packet_map.get("tauri_backend_offline_packaged_ux_review_contract"))
    startup_review = _dict_or_empty(packet_map.get("tauri_backend_startup_runtime_review_contract"))
    config_log_review = _dict_or_empty(packet_map.get("tauri_config_log_runtime_review_contract"))
    signing_review = _dict_or_empty(packet_map.get("tauri_signing_notarization_review_contract"))
    packet_safe = bool(
        packet_map.get("external_calls_triggered") is not True
        and packet_map.get("tushare_called") is not True
        and packet_map.get("deepseek_called") is not True
        and packet_map.get("github_called") is not True
        and packet_map.get("does_not_execute_trades") is not False
        and packet_map.get("does_not_modify_strategy_action") is not False
    )
    artifact_review_ready = bool(
        packet_safe
        and review.get("schema_version") == "tauri_package_artifact_review.v1"
        and review.get("status") == "tauri_package_artifact_review_ready_local_binary"
        and review.get("explicit_review_task_done") is True
        and review.get("local_release_binary_artifact_review_ready") is True
        and review.get("release_binary_exists") is True
        and review.get("release_binary_executable") is True
        and int(review.get("release_binary_size_bytes") or 0) > 0
        and review.get("release_binary_is_completion") is False
        and review.get("production_package_complete") is False
        and review.get("packaged_runtime_validated") is False
        and review.get("packaged_app_launch_qa_done") is False
        and review.get("tauri_build_executed_by_review") is False
        and review.get("npm_or_cargo_executed_by_review") is False
        and review.get("tauri_runtime_started_by_review") is False
        and review.get("packaged_app_opened_by_review") is False
        and review.get("fastapi_started_by_review") is False
        and review.get("config_values_read_by_review") is False
        and review.get("log_files_written_by_review") is False
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("contains_secret") is False
    )
    build_repeatability_ready = bool(
        artifact_review_ready
        and review.get("explicit_tauri_build_completed_before_review") is True
        and review.get("tauri_build_repeatability_done") is True
        and review.get("tauri_build_repeatability_is_completion") is False
        and review.get("build_command_reviewed_safe") in {"npm run tauri build", "cd desktop && npm run tauri build"}
        and review.get("release_binary_modified_at")
    )
    app_bundle_ready = bool(
        artifact_review_ready
        and review.get("app_bundle_artifact_qa_done") is True
        and review.get("app_bundle_detected") is True
        and review.get("app_bundle_is_completion") is False
        and int(review.get("bundle_app_count") or 0) > 0
        and review.get("app_bundle_path")
    )
    dmg_distribution_ready = bool(
        artifact_review_ready
        and review.get("dmg_distribution_artifact_qa_done") is True
        and review.get("dmg_distribution_detected") is True
        and review.get("dmg_distribution_is_completion") is False
        and int(review.get("bundle_dmg_count") or 0) > 0
        and review.get("dmg_distribution_path")
    )
    packaged_app_launch_ready = bool(
        packet_safe
        and app_bundle_ready
        and launch_review.get("schema_version") == "tauri_packaged_runtime_launch_review.v1"
        and launch_review.get("status") == "tauri_packaged_runtime_launch_review_ready_local_launch_smoke"
        and launch_review.get("explicit_review_task_done") is True
        and launch_review.get("local_packaged_app_launch_review_ready") is True
        and launch_review.get("explicit_packaged_app_launch_completed_before_review") is True
        and launch_review.get("app_process_observed_after_launch") is True
        and launch_review.get("packaged_app_launch_smoke_done") is True
        and launch_review.get("packaged_app_launch_qa_done") is True
        and launch_review.get("packaged_app_launch_is_completion") is False
        and launch_review.get("packaged_runtime_validated") is False
        and launch_review.get("production_package_complete") is False
        and launch_review.get("fastapi_started_by_review") is False
        and launch_review.get("config_values_read_by_review") is False
        and launch_review.get("log_files_written_by_review") is False
        and launch_review.get("external_calls_triggered") is False
        and launch_review.get("tushare_called") is False
        and launch_review.get("deepseek_called") is False
        and launch_review.get("github_called") is False
        and launch_review.get("does_not_execute_trades") is True
        and launch_review.get("does_not_modify_strategy_action") is True
        and launch_review.get("contains_secret") is False
    )
    direct_stage_keys = ["release_binary_artifact_qa"] if artifact_review_ready else []
    if build_repeatability_ready:
        direct_stage_keys.append("tauri_build_repeatability")
    if app_bundle_ready:
        direct_stage_keys.append("app_bundle_artifact_qa")
    if dmg_distribution_ready:
        direct_stage_keys.append("dmg_distribution_artifact_qa")
    if packaged_app_launch_ready:
        direct_stage_keys.append("packaged_app_launch_smoke")
    backend_offline_packaged_ux_ready = bool(
        packet_safe
        and packaged_app_launch_ready
        and offline_ux_review.get("schema_version") == "tauri_backend_offline_packaged_ux_review.v1"
        and offline_ux_review.get("status") == "tauri_backend_offline_packaged_ux_review_ready"
        and offline_ux_review.get("explicit_review_task_done") is True
        and offline_ux_review.get("local_backend_offline_packaged_ux_review_ready") is True
        and offline_ux_review.get("backend_was_offline_during_review") is True
        and offline_ux_review.get("offline_notice_observed") is True
        and offline_ux_review.get("fastapi_guidance_visible") is True
        and offline_ux_review.get("local_only_boundary_visible") is True
        and offline_ux_review.get("no_provider_model_github_trade_visible") is True
        and len(str(offline_ux_review.get("screenshot_sha256") or "")) == 64
        and offline_ux_review.get("backend_offline_packaged_ux_verified") is True
        and offline_ux_review.get("backend_offline_packaged_ux_is_completion") is False
        and offline_ux_review.get("packaged_runtime_validated") is False
        and offline_ux_review.get("production_package_complete") is False
        and offline_ux_review.get("fastapi_started_by_review") is False
        and offline_ux_review.get("config_values_read_by_review") is False
        and offline_ux_review.get("log_files_written_by_review") is False
        and offline_ux_review.get("external_calls_triggered") is False
        and offline_ux_review.get("tushare_called") is False
        and offline_ux_review.get("deepseek_called") is False
        and offline_ux_review.get("github_called") is False
        and offline_ux_review.get("does_not_execute_trades") is True
        and offline_ux_review.get("does_not_modify_strategy_action") is True
        and offline_ux_review.get("contains_secret") is False
    )
    if backend_offline_packaged_ux_ready:
        direct_stage_keys.append("backend_offline_packaged_ux")
    backend_startup_runtime_ready = bool(
        packet_safe
        and packaged_app_launch_ready
        and backend_offline_packaged_ux_ready
        and startup_review.get("schema_version") == "tauri_backend_startup_runtime_review.v1"
        and startup_review.get("status") == "tauri_backend_startup_runtime_review_ready"
        and startup_review.get("explicit_review_task_done") is True
        and startup_review.get("local_backend_startup_runtime_review_ready") is True
        and startup_review.get("manual_fastapi_started_before_review") is True
        and startup_review.get("fastapi_health_observed_ok") is True
        and startup_review.get("packaged_app_fastapi_online_observed") is True
        and startup_review.get("api_base_observed_safe") in {"http://127.0.0.1:8710", "http://localhost:8710"}
        and startup_review.get("health_status_observed") in {"ok", "ready", "healthy"}
        and len(str(startup_review.get("screenshot_sha256") or "")) == 64
        and startup_review.get("backend_startup_runtime_validated") is True
        and startup_review.get("backend_startup_runtime_is_completion") is False
        and startup_review.get("backend_sidecar_autostart_validated") is False
        and startup_review.get("packaged_runtime_validated") is False
        and startup_review.get("production_package_complete") is False
        and startup_review.get("fastapi_started_by_review") is False
        and startup_review.get("config_values_read_by_review") is False
        and startup_review.get("log_files_written_by_review") is False
        and startup_review.get("external_calls_triggered") is False
        and startup_review.get("tushare_called") is False
        and startup_review.get("deepseek_called") is False
        and startup_review.get("github_called") is False
        and startup_review.get("does_not_execute_trades") is True
        and startup_review.get("does_not_modify_strategy_action") is True
        and startup_review.get("contains_secret") is False
    )
    if backend_startup_runtime_ready:
        direct_stage_keys.append("backend_startup_runtime")
    config_log_runtime_ready = bool(
        packet_safe
        and backend_startup_runtime_ready
        and config_log_review.get("schema_version") == "tauri_config_log_runtime_review.v1"
        and config_log_review.get("status") == "tauri_config_log_runtime_review_ready"
        and config_log_review.get("explicit_review_task_done") is True
        and config_log_review.get("local_config_log_runtime_review_ready") is True
        and config_log_review.get("path_policy_panel_visible") is True
        and config_log_review.get("config_file_policy_visible") is True
        and config_log_review.get("log_file_policy_visible") is True
        and bool(config_log_review.get("config_file_policy_observed_safe"))
        and bool(config_log_review.get("log_file_policy_observed_safe"))
        and config_log_review.get("no_config_values_exposed") is True
        and config_log_review.get("no_log_file_written_by_review") is True
        and config_log_review.get("frontend_token_exposure_absent") is True
        and len(str(config_log_review.get("screenshot_sha256") or "")) == 64
        and config_log_review.get("config_log_runtime_paths_validated") is True
        and config_log_review.get("config_log_runtime_paths_is_completion") is False
        and config_log_review.get("packaged_runtime_validated") is False
        and config_log_review.get("production_package_complete") is False
        and config_log_review.get("fastapi_started_by_review") is False
        and config_log_review.get("config_values_read_by_review") is False
        and config_log_review.get("log_files_written_by_review") is False
        and config_log_review.get("external_calls_triggered") is False
        and config_log_review.get("tushare_called") is False
        and config_log_review.get("deepseek_called") is False
        and config_log_review.get("github_called") is False
        and config_log_review.get("does_not_execute_trades") is True
        and config_log_review.get("does_not_modify_strategy_action") is True
        and config_log_review.get("contains_secret") is False
    )
    if config_log_runtime_ready:
        direct_stage_keys.append("config_log_runtime_paths")
    signing_notarization_review_ready = bool(
        packet_safe
        and config_log_runtime_ready
        and signing_review.get("schema_version") == "tauri_signing_notarization_review.v1"
        and signing_review.get("status")
        in {
            "tauri_signing_notarization_review_ready_blocked",
            "tauri_signing_notarization_review_ready_passed",
        }
        and signing_review.get("explicit_review_task_done") is True
        and signing_review.get("explicit_codesign_inspection_completed") is True
        and signing_review.get("explicit_spctl_assessment_completed") is True
        and signing_review.get("local_signing_notarization_review_ready") is True
        and bool(signing_review.get("app_bundle_path_observed_safe"))
        and bool(signing_review.get("codesign_signature_type"))
        and bool(signing_review.get("codesign_cdhash_observed_safe"))
        and bool(signing_review.get("spctl_assessment_status"))
        and signing_review.get("signing_notarization_is_completion") is False
        and signing_review.get("production_package_complete") is False
        and signing_review.get("packaged_runtime_validated") is False
        and signing_review.get("fastapi_started_by_review") is False
        and signing_review.get("config_values_read_by_review") is False
        and signing_review.get("log_files_written_by_review") is False
        and signing_review.get("external_calls_triggered") is False
        and signing_review.get("tushare_called") is False
        and signing_review.get("deepseek_called") is False
        and signing_review.get("github_called") is False
        and signing_review.get("does_not_execute_trades") is True
        and signing_review.get("does_not_modify_strategy_action") is True
        and signing_review.get("contains_secret") is False
    )
    signing_notarization_done = bool(
        signing_notarization_review_ready
        and signing_review.get("production_signing_notarization_ready") is True
        and signing_review.get("signing_notarization_done") is True
    )
    direct_gap_stage_keys = (
        list(signing_review.get("direct_gap_evidence_stage_keys") or [])
        if signing_notarization_review_ready
        else []
    )
    return {
        "schema_version": "migration_tauri_package_direct_evidence_summary.v1",
        "source_packet_key": "command_center_3_tauri_package_artifact_review_packet",
        "status": "tauri_package_release_binary_direct_evidence_visible_production_pending"
        if direct_stage_keys
        else "tauri_package_release_binary_direct_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "release_binary_artifact_qa_done": artifact_review_ready,
        "tauri_build_repeatability_done": build_repeatability_ready,
        "app_bundle_artifact_qa_done": app_bundle_ready,
        "dmg_distribution_artifact_qa_done": dmg_distribution_ready,
        "packaged_app_launch_smoke_done": packaged_app_launch_ready,
        "packaged_app_launch_qa_done": packaged_app_launch_ready,
        "backend_offline_packaged_ux_verified": backend_offline_packaged_ux_ready,
        "backend_offline_packaged_ux_screenshot_sha256": offline_ux_review.get("screenshot_sha256")
        if backend_offline_packaged_ux_ready
        else "",
        "backend_offline_packaged_ux_observed_route": offline_ux_review.get("observed_route")
        if backend_offline_packaged_ux_ready
        else "",
        "backend_startup_runtime_validated": backend_startup_runtime_ready,
        "backend_startup_runtime_screenshot_sha256": startup_review.get("screenshot_sha256")
        if backend_startup_runtime_ready
        else "",
        "backend_startup_api_base_observed": startup_review.get("api_base_observed_safe")
        if backend_startup_runtime_ready
        else "",
        "backend_startup_health_status_observed": startup_review.get("health_status_observed")
        if backend_startup_runtime_ready
        else "",
        "config_log_runtime_screenshot_sha256": config_log_review.get("screenshot_sha256")
        if config_log_runtime_ready
        else "",
        "config_file_policy_observed": config_log_review.get("config_file_policy_observed_safe")
        if config_log_runtime_ready
        else "",
        "log_file_policy_observed": config_log_review.get("log_file_policy_observed_safe")
        if config_log_runtime_ready
        else "",
        "direct_gap_evidence_stage_keys": direct_gap_stage_keys,
        "direct_gap_evidence_stage_count": len(direct_gap_stage_keys),
        "signing_notarization_review_ready": signing_notarization_review_ready,
        "signing_notarization_review_status": signing_review.get("status")
        if signing_notarization_review_ready
        else "",
        "codesign_signature_type": signing_review.get("codesign_signature_type")
        if signing_notarization_review_ready
        else "",
        "codesign_team_identifier_status": signing_review.get("codesign_team_identifier_status")
        if signing_notarization_review_ready
        else "",
        "spctl_assessment_status": signing_review.get("spctl_assessment_status")
        if signing_notarization_review_ready
        else "",
        "spctl_message_safe": signing_review.get("spctl_message_safe")
        if signing_notarization_review_ready
        else "",
        "temporary_dmg_detected": signing_review.get("temporary_dmg_detected") is True
        if signing_notarization_review_ready
        else False,
        "temporary_dmg_ignored_for_distribution": signing_review.get("temporary_dmg_ignored_for_distribution") is True
        if signing_notarization_review_ready
        else False,
        "production_signing_notarization_ready": signing_review.get("production_signing_notarization_ready") is True
        if signing_notarization_review_ready
        else False,
        "build_command_reviewed_safe": review.get("build_command_reviewed_safe") if build_repeatability_ready else "",
        "launch_command_reviewed_safe": launch_review.get("launch_command_reviewed_safe")
        if packaged_app_launch_ready
        else "",
        "observed_process_name": launch_review.get("observed_process_name") if packaged_app_launch_ready else "",
        "release_binary_path": review.get("release_binary_path") if artifact_review_ready else "",
        "release_binary_size_bytes": review.get("release_binary_size_bytes") if artifact_review_ready else 0,
        "release_binary_modified_at": review.get("release_binary_modified_at") if artifact_review_ready else "",
        "app_bundle_path": review.get("app_bundle_path") if app_bundle_ready else "",
        "dmg_distribution_path": review.get("dmg_distribution_path") if dmg_distribution_ready else "",
        "temporary_dmg_count": review.get("temporary_dmg_count") if artifact_review_ready else 0,
        "temporary_dmg_ignored_for_distribution": review.get("temporary_dmg_ignored_for_distribution") is True,
        "app_bundle_detected": app_bundle_ready,
        "dmg_distribution_detected": dmg_distribution_ready,
        "packaged_runtime_qa_done": False,
        "backend_startup_runtime_validated": backend_startup_runtime_ready,
        "backend_offline_packaged_ux_verified": backend_offline_packaged_ux_ready,
        "config_log_runtime_paths_validated": config_log_runtime_ready,
        "signing_notarization_done": signing_notarization_done,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_tauri_package_artifact_review"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": "package_artifact_qa_is_not_packaged_runtime_or_production_package",
    }


def _latest_candidate_radar_direct_evidence_summary() -> dict[str, Any]:
    try:
        from server.services import candidate_service

        packet = candidate_service.read_candidate_radar_cache()
    except Exception:
        packet = {}
    packet_map = packet if isinstance(packet, dict) else {}
    policy = _dict_or_empty(packet_map.get("policy"))
    task_pipeline = _dict_or_empty(packet_map.get("fast_scan_task_pipeline_contract"))
    full_pool = _dict_or_empty(packet_map.get("full_pool_local_execution_receipt"))
    deep_scan = _dict_or_empty(packet_map.get("deep_scan_local_review_receipt"))
    full_pool_worker_fallback = _dict_or_empty(packet_map.get("candidate_radar_full_pool_worker_fallback_receipt"))
    deep_scan_worker_fallback = _dict_or_empty(packet_map.get("candidate_radar_deep_scan_worker_fallback_receipt"))
    browser_review = _dict_or_empty(packet_map.get("candidate_browser_qa_review_contract"))
    production_review = _dict_or_empty(packet_map.get("candidate_radar_production_replacement_review_receipt"))
    legacy_retirement_review = _dict_or_empty(
        packet_map.get("candidate_radar_legacy_retirement_review_receipt")
    )

    packet_safe = bool(
        packet_map.get("external_calls_triggered") is False
        and packet_map.get("tushare_called") is False
        and packet_map.get("deepseek_called") is False
        and packet_map.get("github_called") is False
        and packet_map.get("does_not_execute_trades") is True
        and packet_map.get("does_not_modify_strategy_action") is True
        and packet_map.get("candidate_is_not_buy_instruction") is not False
        and packet_map.get("contains_secret") is False
    )
    cache_render_done = bool(
        packet_safe
        and policy.get("does_not_scan_market") is True
        and policy.get("post_task_required_for_scan") is True
        and policy.get("does_not_call_tushare") is True
        and policy.get("does_not_call_deepseek") is True
        and policy.get("does_not_call_github") is True
    )
    quick_task_pipeline_done = bool(
        packet_safe
        and task_pipeline.get("schema_version") == "candidate_radar_fast_scan_task_pipeline.v1"
        and task_pipeline.get("status") == "fast_scan_task_pipeline_ready_local_only"
        and task_pipeline.get("local_task_pipeline_ready") is True
        and int(task_pipeline.get("local_blocker_count") or 0) == 0
        and task_pipeline.get("external_calls_triggered") is False
        and task_pipeline.get("tushare_called") is False
        and task_pipeline.get("deepseek_called") is False
        and task_pipeline.get("github_called") is False
        and task_pipeline.get("does_not_execute_trades") is True
        and task_pipeline.get("does_not_modify_strategy_action") is True
        and task_pipeline.get("candidate_is_not_buy_instruction") is not False
        and task_pipeline.get("contains_secret") is not True
    )
    local_full_pool_done = bool(
        packet_safe
        and full_pool.get("schema_version") == "candidate_radar_full_pool_local_execution_receipt.v1"
        and full_pool.get("status") == "full_pool_local_execution_ready_production_pending"
        and full_pool.get("local_full_pool_execution_done") is True
        and int(full_pool.get("candidate_row_count") or 0) > 0
        and int(full_pool.get("local_blocker_count") or 0) == 0
        and full_pool.get("production_full_pool_scan_done") is False
        and full_pool.get("full_pool_scan_done") is False
        and full_pool.get("provider_backed_acceptance_done") is False
        and full_pool.get("worker_backed_execution_done") is False
        and full_pool.get("external_calls_triggered") is False
        and full_pool.get("tushare_called") is False
        and full_pool.get("deepseek_called") is False
        and full_pool.get("github_called") is False
        and full_pool.get("does_not_execute_trades") is True
        and full_pool.get("does_not_modify_strategy_action") is True
        and full_pool.get("candidate_is_not_buy_instruction") is True
    )
    local_deep_scan_done = bool(
        packet_safe
        and deep_scan.get("schema_version") == "candidate_radar_deep_scan_local_review_receipt.v1"
        and deep_scan.get("status") == "deep_scan_local_review_ready_production_pending"
        and deep_scan.get("local_deep_scan_review_done") is True
        and int(deep_scan.get("reviewed_candidate_count") or 0) > 0
        and int(deep_scan.get("local_blocker_count") or 0) == 0
        and deep_scan.get("deep_scan_done") is False
        and deep_scan.get("deep_scan_validation_done") is False
        and deep_scan.get("provider_backed_acceptance_done") is False
        and deep_scan.get("worker_backed_execution_done") is False
        and deep_scan.get("external_calls_triggered") is False
        and deep_scan.get("tushare_called") is False
        and deep_scan.get("deepseek_called") is False
        and deep_scan.get("github_called") is False
        and deep_scan.get("does_not_execute_trades") is True
        and deep_scan.get("does_not_modify_strategy_action") is True
        and deep_scan.get("candidate_is_not_buy_instruction") is True
    )
    worker_full_pool_fallback_done = bool(
        packet_safe
        and full_pool_worker_fallback.get("schema_version") == "candidate_radar_full_pool_worker_fallback.v1"
        and full_pool_worker_fallback.get("status")
        == "candidate_radar_full_pool_worker_fallback_ready_worker_runtime_pending"
        and full_pool_worker_fallback.get("explicit_full_pool_worker_fallback_done") is True
        and full_pool_worker_fallback.get("operator_approved") is True
        and full_pool_worker_fallback.get("worker_execution_request_ready") is True
        and full_pool_worker_fallback.get("requested_worker_execution_scope_hash_matches_latest") is True
        and full_pool_worker_fallback.get("local_worker_fallback_full_pool_done") is True
        and full_pool_worker_fallback.get("local_worker_fallback_ready") is True
        and int(full_pool_worker_fallback.get("candidate_row_count") or 0) > 0
        and int(full_pool_worker_fallback.get("local_blocker_count") or 0) == 0
        and int(full_pool_worker_fallback.get("production_blocker_count") or 0) > 0
        and full_pool_worker_fallback.get("production_full_pool_scan_done") is False
        and full_pool_worker_fallback.get("full_pool_scan_done") is False
        and full_pool_worker_fallback.get("provider_backed_acceptance_done") is False
        and full_pool_worker_fallback.get("worker_backed_execution_done") is False
        and full_pool_worker_fallback.get("worker_execution_implemented") is False
        and full_pool_worker_fallback.get("worker_started") is False
        and full_pool_worker_fallback.get("worker_task_created") is False
        and full_pool_worker_fallback.get("worker_task_executed") is False
        and full_pool_worker_fallback.get("redis_broker_used") is False
        and full_pool_worker_fallback.get("celery_worker_started") is False
        and full_pool_worker_fallback.get("cache_get_external_calls") is False
        and full_pool_worker_fallback.get("react_render_external_calls") is False
        and full_pool_worker_fallback.get("external_calls_triggered") is False
        and full_pool_worker_fallback.get("tushare_called") is False
        and full_pool_worker_fallback.get("deepseek_called") is False
        and full_pool_worker_fallback.get("github_called") is False
        and full_pool_worker_fallback.get("does_not_execute_trades") is True
        and full_pool_worker_fallback.get("does_not_modify_strategy_action") is True
        and full_pool_worker_fallback.get("candidate_is_not_buy_instruction") is True
        and full_pool_worker_fallback.get("contains_secret") is False
    )
    worker_deep_scan_fallback_done = bool(
        packet_safe
        and deep_scan_worker_fallback.get("schema_version") == "candidate_radar_deep_scan_worker_fallback.v1"
        and deep_scan_worker_fallback.get("status")
        == "candidate_radar_deep_scan_worker_fallback_ready_worker_runtime_pending"
        and deep_scan_worker_fallback.get("explicit_deep_scan_worker_fallback_done") is True
        and deep_scan_worker_fallback.get("operator_approved") is True
        and deep_scan_worker_fallback.get("worker_execution_request_ready") is True
        and deep_scan_worker_fallback.get("requested_worker_execution_scope_hash_matches_latest") is True
        and deep_scan_worker_fallback.get("local_deep_scan_review_done") is True
        and deep_scan_worker_fallback.get("local_worker_fallback_deep_scan_done") is True
        and deep_scan_worker_fallback.get("local_worker_fallback_ready") is True
        and int(deep_scan_worker_fallback.get("candidate_row_count") or 0) > 0
        and int(deep_scan_worker_fallback.get("local_blocker_count") or 0) == 0
        and int(deep_scan_worker_fallback.get("production_blocker_count") or 0) > 0
        and deep_scan_worker_fallback.get("production_deep_scan_done") is False
        and deep_scan_worker_fallback.get("deep_scan_done") is False
        and deep_scan_worker_fallback.get("provider_backed_acceptance_done") is False
        and deep_scan_worker_fallback.get("worker_backed_execution_done") is False
        and deep_scan_worker_fallback.get("worker_deep_scan_execution_done") is False
        and deep_scan_worker_fallback.get("worker_execution_implemented") is False
        and deep_scan_worker_fallback.get("model_execution_implemented") is False
        and deep_scan_worker_fallback.get("deepseek_model_execution_done") is False
        and deep_scan_worker_fallback.get("deepseek_model_ledger_complete") is False
        and deep_scan_worker_fallback.get("worker_started") is False
        and deep_scan_worker_fallback.get("worker_task_created") is False
        and deep_scan_worker_fallback.get("worker_task_executed") is False
        and deep_scan_worker_fallback.get("redis_broker_used") is False
        and deep_scan_worker_fallback.get("celery_worker_started") is False
        and deep_scan_worker_fallback.get("cache_get_external_calls") is False
        and deep_scan_worker_fallback.get("react_render_external_calls") is False
        and deep_scan_worker_fallback.get("external_calls_triggered") is False
        and deep_scan_worker_fallback.get("tushare_called") is False
        and deep_scan_worker_fallback.get("deepseek_called") is False
        and deep_scan_worker_fallback.get("github_called") is False
        and deep_scan_worker_fallback.get("does_not_execute_trades") is True
        and deep_scan_worker_fallback.get("does_not_modify_strategy_action") is True
        and deep_scan_worker_fallback.get("candidate_is_not_buy_instruction") is True
        and deep_scan_worker_fallback.get("contains_secret") is False
    )
    browser_visual_performance_done = bool(
        packet_safe
        and browser_review.get("schema_version") == "candidate_radar_browser_qa_review.v1"
        and browser_review.get("status") == "candidate_browser_qa_review_ready_local_artifact"
        and browser_review.get("explicit_review_task_done") is True
        and browser_review.get("local_browser_qa_review_ready") is True
        and (
            browser_review.get("candidate_browser_qa_evidence_found") is True
            or int(browser_review.get("evidence_row_count") or 0) > 0
        )
        and browser_review.get("candidate_visual_qa_evidence_passed") is True
        and browser_review.get("candidate_browser_performance_evidence_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
        and int(browser_review.get("review_required_count") or 0) == 0
        and browser_review.get("opens_no_browser") is True
        and browser_review.get("starts_no_servers") is True
        and browser_review.get("production_radar_replacement_complete") is False
        and browser_review.get("external_calls_triggered") is False
        and browser_review.get("tushare_called") is False
        and browser_review.get("deepseek_called") is False
        and browser_review.get("github_called") is False
        and browser_review.get("does_not_execute_trades") is True
        and browser_review.get("does_not_modify_strategy_action") is True
        and browser_review.get("candidate_is_not_buy_instruction") is True
    )
    production_review_ready = bool(
        production_review.get("schema_version") == "candidate_radar_production_replacement_review.v1"
        and production_review.get("status") == "candidate_radar_production_replacement_review_ready_production_blocked"
        and production_review.get("local_review_ready") is True
        and production_review.get("production_radar_replacement_complete") is False
        and production_review.get("external_calls_triggered") is False
        and production_review.get("tushare_called") is False
        and production_review.get("deepseek_called") is False
        and production_review.get("github_called") is False
    )
    legacy_retirement_review_done = bool(
        packet_safe
        and legacy_retirement_review.get("schema_version") == "candidate_radar_legacy_retirement_review.v1"
        and legacy_retirement_review.get("status")
        == "candidate_radar_legacy_retirement_review_ready_retirement_blocked"
        and legacy_retirement_review.get("explicit_legacy_retirement_review_done") is True
        and legacy_retirement_review.get("operator_approved") is True
        and legacy_retirement_review.get("local_review_ready") is True
        and legacy_retirement_review.get("ready_to_retire_legacy") is False
        and legacy_retirement_review.get("legacy_retirement_ready") is False
        and legacy_retirement_review.get("legacy_fallback_required") is True
        and legacy_retirement_review.get("production_radar_replacement_complete") is False
        and legacy_retirement_review.get("production_replacement_review_ready") is True
        and legacy_retirement_review.get("production_promotion_dry_run_visible") is True
        and int(legacy_retirement_review.get("local_blocker_count") or 0) == 0
        and int(legacy_retirement_review.get("production_blocker_count") or 0) > 0
        and legacy_retirement_review.get("cache_get_external_calls") is False
        and legacy_retirement_review.get("react_render_external_calls") is False
        and legacy_retirement_review.get("external_calls_triggered") is False
        and legacy_retirement_review.get("tushare_called") is False
        and legacy_retirement_review.get("deepseek_called") is False
        and legacy_retirement_review.get("github_called") is False
        and legacy_retirement_review.get("worker_started") is False
        and legacy_retirement_review.get("creates_worker_task") is False
        and legacy_retirement_review.get("creates_provider_model_task") is False
        and legacy_retirement_review.get("contains_secret") is False
        and legacy_retirement_review.get("does_not_execute_trades") is True
        and legacy_retirement_review.get("does_not_modify_strategy_action") is True
        and legacy_retirement_review.get("candidate_is_not_buy_instruction") is True
    )
    direct_stage_keys = []
    if cache_render_done:
        direct_stage_keys.append("cache_render_boundary")
    if quick_task_pipeline_done:
        direct_stage_keys.append("quick_scan_task_pipeline")
    if local_full_pool_done:
        direct_stage_keys.append("local_full_pool_execution_receipt")
    if local_deep_scan_done:
        direct_stage_keys.append("local_deep_scan_review_receipt")
    if worker_full_pool_fallback_done:
        direct_stage_keys.append("worker_full_pool_fallback_execution")
    if worker_deep_scan_fallback_done:
        direct_stage_keys.append("worker_deep_scan_fallback_execution")
    if browser_visual_performance_done:
        direct_stage_keys.append("browser_visual_performance_promotion")
    if legacy_retirement_review_done:
        direct_stage_keys.append("legacy_retirement_review")

    return {
        "schema_version": "migration_candidate_radar_direct_evidence_summary.v1",
        "source_packet_key": "command_center_3_candidate_radar_cache",
        "status": "candidate_radar_direct_evidence_visible_production_pending"
        if direct_stage_keys
        else "candidate_radar_direct_evidence_missing",
        "available": bool(direct_stage_keys),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "cache_render_boundary_verified": cache_render_done,
        "quick_scan_task_pipeline_verified": quick_task_pipeline_done,
        "local_full_pool_execution_receipt_verified": local_full_pool_done,
        "local_deep_scan_review_receipt_verified": local_deep_scan_done,
        "worker_full_pool_fallback_execution_verified": worker_full_pool_fallback_done,
        "worker_deep_scan_fallback_execution_verified": worker_deep_scan_fallback_done,
        "browser_visual_performance_evidence_verified": browser_visual_performance_done,
        "production_replacement_review_ready": production_review_ready,
        "legacy_retirement_review_direct_evidence_verified": legacy_retirement_review_done,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "provider_backed_acceptance_done": False,
        "worker_backed_execution_done": False,
        "browser_visual_delta_qa_done": browser_visual_performance_done,
        "browser_performance_trace_done": browser_visual_performance_done,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "direct_evidence_layer": "L3_local_candidate_radar_worker_fallback_browser_safety_evidence"
        if worker_full_pool_fallback_done or worker_deep_scan_fallback_done
        else "L3_local_candidate_radar_scan_browser_safety_evidence"
        if direct_stage_keys
        else "L1_static_contract",
        "evidence_boundary": (
            "candidate_radar_local_scan_browser_evidence_is_not_production_replacement"
        ),
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
        "POST /api/factor-quant/universe-worker-batch-dry-run": {
            "step_kind": "factor_universe_worker_batch_scope_ticket",
            "safe_payload_summary": "approved_by_user, universe_mode=full_pool, requested stages, no worker/provider execution",
            "expected_local_receipt": "universe_worker_batch_dry_run_receipt",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/factor-quant/universe-worker-batch-execution-request": {
            "step_kind": "scope_bound_factor_universe_worker_batch_execution_request",
            "safe_payload_summary": "approved_by_user plus latest Factor universe worker-batch dry-run scope hash",
            "expected_local_receipt": "universe_worker_batch_execution_request_receipt",
            "required_prior_phase_key": "factor_universe_worker_batch_dry_run_scope_ticket",
            "required_prior_material": "receipt_scope_hash",
        },
        "POST /api/factor-quant/universe-worker-batch-research": {
            "step_kind": "local_factor_universe_worker_batch_research_receipt",
            "safe_payload_summary": "approved_by_user plus latest Factor universe execution-request scope hash; local receipt only",
            "expected_local_receipt": "universe_worker_batch_research_receipt",
            "required_prior_phase_key": "factor_universe_worker_batch_execution_request_ticket",
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
            "context_key": "candidate_radar_production_replacement_review_preview",
        },
        "POST /api/candidate-radar/legacy-retirement-review": {
            "step_kind": "local_candidate_radar_legacy_retirement_review",
            "safe_payload_summary": "operator_approved plus latest promotion dry-run scope hash; local review only",
            "expected_local_receipt": "candidate_radar_legacy_retirement_review_receipt",
            "required_prior_phase_key": "radar_production_promotion_dry_run_ticket",
            "required_prior_material": "receipt_scope_hash",
        },
        "POST /api/candidate-radar/production-promotion-review": {
            "step_kind": "local_candidate_radar_production_promotion_review",
            "safe_payload_summary": "operator_approved plus latest promotion dry-run scope hash after legacy-retirement review; local review only",
            "expected_local_receipt": "candidate_radar_production_promotion_review_receipt",
            "required_prior_phase_key": "radar_production_promotion_dry_run_ticket",
            "required_prior_material": "receipt_scope_hash",
        },
        "POST /api/storage/backtest-results/schema-seed": {
            "step_kind": "local_backtest_results_zero_row_schema_seed",
            "safe_payload_summary": "confirm_schema_seed=true; writes only ignored local backtest_results Parquet empty schema, no mock rows, no provider",
            "expected_local_receipt": "backtest_results_schema_seed_evidence",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/storage/schema-validation/acceptance": {
            "step_kind": "local_storage_schema_validation_acceptance",
            "safe_payload_summary": "source only; reads local Parquet schema metadata, no row payload, no write, no provider",
            "expected_local_receipt": "schema_validation_acceptance_evidence",
            "required_prior_phase_key": "storage_backtest_results_schema_seed_receipt",
            "required_prior_material": "",
        },
        "POST /api/storage/dataset-version-manifest/dry-run": {
            "step_kind": "local_storage_manifest_dry_run",
            "safe_payload_summary": "source only; builds local manifest write plan, no manifest write, no Parquet write, no provider",
            "expected_local_receipt": "storage_dataset_version_manifest_dry_run",
            "required_prior_phase_key": "storage_schema_validation_acceptance_receipt",
            "required_prior_material": "",
        },
        "POST /api/storage/dataset-version-manifest/review": {
            "step_kind": "local_storage_manifest_review",
            "safe_payload_summary": "source only; reviews schema acceptance plus manifest dry-run, no manifest write, no provider",
            "expected_local_receipt": "storage_dataset_version_manifest_review",
            "required_prior_phase_key": "storage_dataset_version_manifest_dry_run_receipt",
            "required_prior_material": "",
        },
        "POST /api/storage/dataset-version-manifest/write": {
            "step_kind": "local_storage_manifest_write",
            "safe_payload_summary": "confirm_manifest_write=true after review; writes only ignored local _dataset_versions.json, no Parquet write, no provider",
            "expected_local_receipt": "storage_dataset_version_manifest_write",
            "required_prior_phase_key": "storage_dataset_version_manifest_review_receipt",
            "required_prior_material": "",
        },
        "POST /api/storage/dataset-version-manifest/validate": {
            "step_kind": "local_storage_manifest_validate",
            "safe_payload_summary": "source only; validates ignored local _dataset_versions.json, no write, no provider",
            "expected_local_receipt": "storage_dataset_version_manifest_validate",
            "required_prior_phase_key": "storage_dataset_version_manifest_write_receipt",
            "required_prior_material": "",
        },
        "POST /api/storage/physical-execution-request": {
            "step_kind": "scope_bound_physical_execution_request",
            "safe_payload_summary": "approved_by_user plus latest storage physical execution recipe scope hash",
            "expected_local_receipt": "storage_physical_execution_request",
            "required_prior_phase_key": "storage_dataset_version_manifest_validate_receipt",
            "required_prior_material": "physical_execution_scope_hash",
            "manual_scope_hash_required": True,
            "context_key": "storage_physical_execution_recipe_preview",
        },
        "POST /api/worker/synthetic-healthcheck": {
            "step_kind": "local_synthetic_healthcheck",
            "safe_payload_summary": "requested_from only; local task-store readback, no worker process start",
            "expected_local_receipt": "worker_synthetic_healthcheck",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/worker/activation-review": {
            "step_kind": "local_activation_review",
            "safe_payload_summary": "operator_approved plus latest synthetic healthcheck receipt",
            "expected_local_receipt": "worker_activation_review_task_receipt",
            "required_prior_phase_key": "worker_synthetic_healthcheck_receipt",
            "required_prior_material": "",
        },
        "POST /api/worker/production-evidence-plan": {
            "step_kind": "local_production_evidence_plan",
            "safe_payload_summary": "operator_approved plus latest worker activation review receipt",
            "expected_local_receipt": "worker_production_evidence_plan_receipt",
            "required_prior_phase_key": "worker_activation_review_receipt",
            "required_prior_material": "",
        },
        "POST /api/worker/runtime-qa-execution-request": {
            "step_kind": "scope_bound_runtime_qa_execution_request",
            "safe_payload_summary": "operator_approved plus evidence-plan scope hash and runtime QA recipe scope hash",
            "expected_local_receipt": "worker_runtime_qa_execution_request_receipt",
            "required_prior_phase_key": "worker_production_evidence_plan_receipt",
            "required_prior_material": "receipt_scope_hash",
            "manual_scope_hash_required": True,
            "context_key": "worker_runtime_qa_context_preview",
        },
        "POST /api/worker/runtime-qa-dry-run": {
            "step_kind": "scope_bound_runtime_qa_dry_run",
            "safe_payload_summary": "operator_approved plus latest runtime QA request task id and bound scope hashes",
            "expected_local_receipt": "worker_runtime_qa_dry_run_receipt",
            "required_prior_phase_key": "worker_runtime_qa_execution_request_ticket",
            "required_prior_material": "latest_task_id",
            "manual_scope_hash_required": True,
            "context_key": "worker_runtime_qa_context_preview",
        },
        "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket": {
            "step_kind": "local_model_benchmark_scope_ticket",
            "safe_payload_summary": "approved_by_user, sample_count=40, response_format=json_schema, max_retry_per_sample=2",
            "expected_local_receipt": "deepseek_provider_benchmark_scope_ticket_receipt",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/next-session/browser-qa-review": {
            "step_kind": "local_browser_qa_artifact_review",
            "safe_payload_summary": "review_scope=next_session_browser_qa_local_artifact; reads ignored local reports only",
            "expected_local_receipt": "next_session_browser_qa_review_contract",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/audit/motion-browser-qa-review": {
            "step_kind": "local_motion_browser_qa_artifact_review",
            "safe_payload_summary": "review_scope=motion_browser_qa_local_artifact; reads ignored local reports only",
            "expected_local_receipt": "motion_browser_qa_review_contract",
            "required_prior_phase_key": "",
            "required_prior_material": "",
        },
        "POST /api/audit/motion-production-promotion-dry-run": {
            "step_kind": "local_motion_production_promotion_dry_run",
            "safe_payload_summary": "user_approved, promote_visual=true, promote_performance=true; no browser/GitHub execution",
            "expected_local_receipt": "motion_promotion_dry_run_receipt",
            "required_prior_phase_key": "motion_browser_qa_review_receipt",
            "required_prior_material": "receipt_local_ready",
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
    elif required_material == "receipt_local_ready":
        material_visible = prior_step.get("local_ready") is True
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
    if context_key == "candidate_radar_production_replacement_review_preview":
        prior_visible = bool(context_map.get("review_visible"))
        material_visible = bool(context_map.get("review_scope_hash"))
        manual_scope_hash_required = not bool(context_map.get("can_prebind_review_scope_hash"))
    if context_key == "storage_physical_execution_recipe_preview":
        prior_visible = bool(context_map.get("recipe_visible"))
        material_visible = bool(context_map.get("physical_execution_scope_hash"))
        manual_scope_hash_required = not bool(context_map.get("can_prebind_physical_execution_scope_hash"))
    if context_key == "worker_runtime_qa_context_preview":
        if next_local_step == "POST /api/worker/runtime-qa-execution-request":
            prior_visible = bool(prior_step.get("receipt_visible")) and bool(context_map.get("runtime_qa_recipe_visible"))
            material_visible = bool(context_map.get("evidence_plan_scope_hash")) and bool(
                context_map.get("runtime_qa_scope_hash")
            )
            manual_scope_hash_required = not bool(context_map.get("can_prebind_runtime_qa_execution_request_scope"))
        elif next_local_step == "POST /api/worker/runtime-qa-dry-run":
            prior_visible = bool(prior_step.get("receipt_visible")) and bool(context_map.get("runtime_qa_request_visible"))
            material_visible = bool(
                context_map.get("runtime_qa_request_task_id")
                and context_map.get("runtime_qa_request_evidence_plan_scope_hash")
                and context_map.get("runtime_qa_request_runtime_scope_hash")
            )
            manual_scope_hash_required = not bool(context_map.get("can_prebind_runtime_qa_dry_run_scope"))
    ready_for_clean_receipt = prior_visible and material_visible and not manual_scope_hash_required
    if ready_for_clean_receipt:
        disabled_reason = ""
    elif context_key == "tushare_target_sample_execution_recipe_preview" and not prior_visible:
        disabled_reason = "latest_target_sample_execution_recipe_missing"
    elif context_key == "tushare_target_sample_execution_recipe_preview" and prior_visible and manual_scope_hash_required:
        disabled_reason = "latest_target_sample_execution_recipe_not_ready_for_confirmation"
    elif context_key == "candidate_radar_production_replacement_review_preview" and not prior_visible:
        disabled_reason = "latest_candidate_radar_production_replacement_review_missing"
    elif (
        context_key == "candidate_radar_production_replacement_review_preview"
        and prior_visible
        and not material_visible
    ):
        disabled_reason = "latest_candidate_radar_production_replacement_review_scope_hash_missing"
    elif (
        context_key == "candidate_radar_production_replacement_review_preview"
        and prior_visible
        and manual_scope_hash_required
    ):
        disabled_reason = "latest_candidate_radar_production_replacement_review_not_ready"
    elif context_key == "storage_physical_execution_recipe_preview" and not prior_visible:
        disabled_reason = "latest_storage_physical_execution_recipe_missing"
    elif context_key == "storage_physical_execution_recipe_preview" and prior_visible and not material_visible:
        disabled_reason = "latest_storage_physical_execution_scope_hash_missing"
    elif context_key == "storage_physical_execution_recipe_preview" and prior_visible and manual_scope_hash_required:
        disabled_reason = "latest_storage_physical_execution_recipe_not_ready"
    elif context_key == "worker_runtime_qa_context_preview" and not prior_visible:
        disabled_reason = "latest_worker_runtime_qa_prerequisite_missing"
    elif context_key == "worker_runtime_qa_context_preview" and prior_visible and not material_visible:
        disabled_reason = "latest_worker_runtime_qa_scope_material_missing"
    elif context_key == "worker_runtime_qa_context_preview" and prior_visible and manual_scope_hash_required:
        disabled_reason = "latest_worker_runtime_qa_context_not_ready"
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
            "prepared_context_status": context_map.get("recipe_status") or context_map.get("review_status") or "",
            "prepared_context_source_packet_key": context_map.get("source_packet_key") or "",
            "prepared_context_source_receipt_key": context_map.get("source_receipt_key") or "",
            "prepared_review_scope_hash": context_map.get("review_scope_hash") or "",
            "prepared_review_scope_hash_short": context_map.get("review_scope_hash_short") or "",
            "prepared_physical_execution_scope_hash": context_map.get("physical_execution_scope_hash") or "",
            "prepared_physical_execution_scope_hash_short": context_map.get("physical_execution_scope_hash_short") or "",
            "prepared_evidence_plan_scope_hash": context_map.get("evidence_plan_scope_hash")
            or context_map.get("runtime_qa_request_evidence_plan_scope_hash")
            or "",
            "prepared_evidence_plan_scope_hash_short": context_map.get("evidence_plan_scope_hash_short") or "",
            "prepared_runtime_qa_scope_hash": context_map.get("runtime_qa_scope_hash")
            or context_map.get("runtime_qa_request_runtime_scope_hash")
            or "",
            "prepared_runtime_qa_scope_hash_short": context_map.get("runtime_qa_scope_hash_short") or "",
            "prepared_runtime_qa_request_task_id": context_map.get("runtime_qa_request_task_id") or "",
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
    def _ready_for_future_handoff(row: dict[str, Any]) -> bool:
        return any(
            row.get(key) is True
            for key in (
                "receipt_ready_for_manual_provider_task_submission",
                "receipt_ready_for_manual_worker_task_submission",
                "receipt_ready_for_manual_provider_model_task_submission",
                "receipt_ready_for_manual_physical_task_submission",
                "receipt_ready_for_manual_runtime_qa_task_submission",
            )
        )

    latest_ready_step = next(
        (
            row
            for row in reversed(local_step_rows)
            if row.get("receipt_visible") is True and _ready_for_future_handoff(row)
        ),
        {},
    )
    route = str(
        latest_ready_step.get("receipt_target_post_task_route")
        or (next_local_step if next_local_step.startswith("POST /api/") else "")
    )
    durable_local_receipt = latest_ready_step.get("receipt_durable_in_sqlite") is True
    future_material_visible = bool(
        latest_ready_step.get("receipt_target_payload_present")
        or latest_ready_step.get("receipt_target_task_type")
        or latest_ready_step.get("receipt_target_acceptance_mode")
        or route
    )
    handoff_ready = bool(
        latest_ready_step
        and durable_local_receipt
        and future_material_visible
        and latest_ready_step.get("receipt_creates_provider_task") is False
        and latest_ready_step.get("receipt_provider_task_created") is False
        and latest_ready_step.get("receipt_provider_execution_implemented") is False
        and latest_ready_step.get("receipt_creates_worker_task") is False
        and latest_ready_step.get("receipt_worker_task_created") is False
        and latest_ready_step.get("receipt_worker_execution_implemented") is False
        and latest_ready_step.get("receipt_worker_started") is False
    )
    if handoff_ready:
        if latest_ready_step.get("receipt_ready_for_manual_worker_task_submission") is True:
            status = "future_worker_handoff_preview_ready"
        elif latest_ready_step.get("receipt_ready_for_manual_provider_task_submission") is True:
            status = "future_provider_handoff_preview_ready"
        else:
            status = "future_execution_handoff_preview_ready"
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
            "worker_task_created_by_preview": False,
            "worker_execution_implemented_by_preview": False,
            "worker_started_by_preview": False,
            "requires_separate_user_approved_provider_task": latest_ready_step.get(
                "receipt_ready_for_manual_provider_task_submission"
            )
            is True,
            "requires_separate_user_approved_worker_task": latest_ready_step.get(
                "receipt_ready_for_manual_worker_task_submission"
            )
            is True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "can_close_goal": False,
            "production_complete": False,
            "evidence_boundary": "future_handoff_preview_is_read_only_not_provider_or_worker_execution",
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
        required_local_step_rows = [row for row in local_step_rows if row.get("local_queue_required") is not False]
        observed_steps = [row for row in local_step_rows if row["receipt_visible"] is True]
        observed_required_steps = [row for row in required_local_step_rows if row["receipt_visible"] is True]
        missing_steps = [row for row in required_local_step_rows if row["receipt_visible"] is False]
        ready_steps = [row for row in local_step_rows if row.get("receipt_visible") is True and row.get("local_ready") is True]
        blocked_steps = [
            row
            for row in required_local_step_rows
            if row.get("receipt_visible") is True and row.get("local_ready") is not True
        ]
        first_not_ready_step = next(
            (
                row
                for row in required_local_step_rows
                if not (row.get("receipt_visible") is True and row.get("local_ready") is True)
            ),
            {},
        )
        durable_observed_steps = [row for row in observed_steps if row.get("receipt_durable_in_sqlite") is True]
        memory_only_observed_steps = [row for row in observed_steps if row.get("receipt_memory_only") is True]
        if not local_step_rows:
            local_status = "local_receipt_lookup_not_configured"
            next_local_step = ""
        elif required_local_step_rows and not observed_required_steps:
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
        if action["queue_id"] == "p3_candidate_radar_provider_worker_promotion":
            safe_context["candidate_radar_production_replacement_review_preview"] = (
                _latest_candidate_radar_production_replacement_review_preview()
            )
        if action["queue_id"] == "p4_storage_physical_execution":
            safe_context["storage_physical_execution_recipe_preview"] = (
                _latest_storage_physical_execution_recipe_preview()
            )
        if action["queue_id"] == "p4_worker_runtime_qa":
            safe_context["worker_runtime_qa_context_preview"] = _latest_worker_runtime_qa_context_preview()
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
                "required_local_receipt_step_count": len(required_local_step_rows),
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
    tushare_direct_evidence = _latest_tushare_direct_provider_evidence_summary()
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
        provider_call_ledger_done = (
            tushare_direct_evidence.get("trade_cal_provider_call_ledger_evidence_done") is True
        )
        direct_evidence_count = 1 if provider_call_ledger_done else 0
        direct_evidence_stage_keys = ["trade_cal_provider_call_ledger"] if provider_call_ledger_done else []
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-01",
                "goal": "A 股交易日历级 freshness 生产化",
                "stage_scope_manifest": "freshness_production_stage_scope_manifest",
                "status": "observed_prior_trade_cal_provider_call_ledger_long_window_pending"
                if provider_call_ledger_done
                else "observed_in_data_health_freshness_static_contract"
                if stage_rows
                else "missing_from_data_health_freshness_static_contract",
                "observed_source": "scripts/data_health_freshness_contract._freshness_production_stage_scope_rows local static contract",
                "cache_status": "data_health_freshness_static_contract",
                "cache_mode": "local_static_contract_plus_prior_provider_ledger"
                if provider_call_ledger_done
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count + (1 if provider_call_ledger_done else 0),
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence_stage_keys,
                "production_blocker_count": observed_pending_count,
                "provider_backed_trade_cal_acceptance_done": False,
                "production_freshness_gate_complete": False,
                "real_trade_cal_long_window_validation_done": False,
                "provider_refresh_called_by_contract": False,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": provider_call_ledger_done,
                "provider_direct_evidence_layer": tushare_direct_evidence.get("direct_evidence_layer"),
                "provider_direct_evidence_source": tushare_direct_evidence.get("source_packet_key"),
                "provider_direct_evidence_status": tushare_direct_evidence.get("source_status"),
                "trade_cal_provider_call_ledger_observed_count": int(
                    tushare_direct_evidence.get("trade_cal_provider_call_ledger_observed_count") or 0
                ),
                "trade_cal_provider_observed_row_count": int(
                    tushare_direct_evidence.get("trade_cal_provider_observed_row_count") or 0
                ),
                "trade_cal_provider_call_statuses": list(
                    tushare_direct_evidence.get("trade_cal_provider_call_statuses") or []
                ),
                "safe_trade_cal_call_ledger_fields_present": (
                    tushare_direct_evidence.get("safe_trade_cal_call_ledger_fields_present") is True
                ),
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
                "candidate_is_not_buy_instruction": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_l3_trade_cal_provider_call_ledger_not_production_completion"
                if provider_call_ledger_done
                else "observed_local_static_freshness_stage_scope_not_production_completion",
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
                "direct_evidence_stage_count": 0,
                "direct_evidence_stage_keys": [],
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
                "candidate_is_not_buy_instruction": True,
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
        provider_call_ledger_done = tushare_direct_evidence.get("provider_call_ledger_evidence_done") is True
        direct_evidence_count = 1 if provider_call_ledger_done else 0
        direct_evidence_stage_keys = ["tushare_provider_call_ledger"] if provider_call_ledger_done else []
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        local_evidence_count = sum(
            1 for row in stage_rows if isinstance(row, dict) and row.get("local_stage_evidence_present") is True
        )
        rows.append(
            {
                "id": "LTG-02",
                "goal": "Tushare 全接口生产流水线",
                "stage_scope_manifest": "tushare_production_stage_scope_manifest",
                "status": "observed_prior_tushare_provider_call_ledger_target_acceptance_pending"
                if provider_call_ledger_done
                else "observed_in_tushare_acceptance_static_contract"
                if stage_rows
                else "missing_from_tushare_acceptance_static_contract",
                "observed_source": "scripts/tushare_acceptance_contract._tushare_production_stage_scope_rows local static contract",
                "cache_status": "tushare_acceptance_static_contract",
                "cache_mode": "local_static_contract_plus_prior_provider_ledger"
                if provider_call_ledger_done
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count + (1 if provider_call_ledger_done else 0),
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence_stage_keys,
                "production_blocker_count": observed_pending_count,
                "provider_backed_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "full_interface_acceptance_done": False,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": provider_call_ledger_done,
                "provider_direct_evidence_layer": tushare_direct_evidence.get("direct_evidence_layer"),
                "provider_direct_evidence_source": tushare_direct_evidence.get("source_packet_key"),
                "provider_direct_evidence_status": tushare_direct_evidence.get("source_status"),
                "provider_call_ledger_count": int(tushare_direct_evidence.get("call_ledger_count") or 0),
                "selected_api_count": int(tushare_direct_evidence.get("selected_api_count") or 0),
                "full_interface_selection_done": tushare_direct_evidence.get("full_interface_selection_done")
                is True,
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
                "candidate_is_not_buy_instruction": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_l3_tushare_provider_call_ledger_not_production_completion"
                if provider_call_ledger_done
                else "observed_local_static_tushare_stage_scope_not_production_completion",
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
                "direct_evidence_stage_count": 0,
                "direct_evidence_stage_keys": [],
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
                "candidate_is_not_buy_instruction": True,
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
        direct_evidence = _latest_factor_test_lab_direct_research_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        effective_pending_count = max(pending_count - direct_evidence_count, 0)
        status = (
            "observed_factor_test_lab_direct_evidence_production_pending"
            if stage_rows and direct_evidence_count
            else (
                "observed_in_factor_test_lab_static_contract"
                if stage_rows
                else "missing_from_factor_test_lab_static_contract"
            )
        )
        rows.append(
            {
                "id": "LTG-03",
                "goal": "Factor Test Lab 完整生产化",
                "stage_scope_manifest": "factor_test_production_stage_scope_manifest",
                "status": status,
                "observed_source": (
                    "scripts/factor_test_lab_contract._factor_test_production_stage_scope_rows local static "
                    "contract + read-only factor_quant_cache direct evidence summary"
                ),
                "cache_status": direct_evidence.get("status") or "factor_test_lab_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": effective_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence.get("direct_evidence_stage_keys", []),
                "factor_test_direct_evidence_layer": direct_evidence.get("direct_evidence_layer"),
                "local_light_metric_baseline_verified": direct_evidence.get("local_light_metric_baseline_verified")
                is True,
                "provider_small_pool_scope_ticket_verified": direct_evidence.get(
                    "provider_small_pool_scope_ticket_verified"
                )
                is True,
                "provider_small_pool_dry_run_ready": direct_evidence.get("provider_small_pool_dry_run_ready") is True,
                "provider_small_pool_execution_recipe_ready": direct_evidence.get(
                    "provider_small_pool_execution_recipe_ready"
                )
                is True,
                "provider_small_pool_execution_request_ready": direct_evidence.get(
                    "provider_small_pool_execution_request_ready"
                )
                is True,
                "provider_small_pool_scope_hash_short": direct_evidence.get("provider_small_pool_scope_hash_short")
                or "",
                "production_blocker_count": effective_pending_count,
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
                "evidence_boundary": direct_evidence.get("evidence_boundary")
                or "observed_local_static_factor_test_stage_scope_not_production_completion",
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
        direct_evidence = _latest_factor_universe_direct_research_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        effective_pending_count = max(pending_count - direct_evidence_count, 0)
        rows.append(
            {
                "id": "LTG-04",
                "goal": "Factor 全市场 / 股票池研究",
                "stage_scope_manifest": "factor_universe_worker_batch_stage_scope_manifest",
                "status": (
                    "observed_factor_universe_direct_research_evidence_production_pending"
                    if stage_rows and direct_evidence_count
                    else (
                        "observed_in_factor_universe_static_contract"
                        if stage_rows
                        else "missing_from_factor_universe_static_contract"
                    )
                ),
                "observed_source": (
                    "scripts/factor_universe_contract._worker_stage_scope_rows local static contract + "
                    "read-only factor_quant_cache local rank/zscore evidence summary"
                ),
                "cache_status": direct_evidence.get("status") or "factor_universe_static_contract",
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": effective_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence.get("direct_evidence_stage_keys", []),
                "factor_universe_direct_evidence_layer": direct_evidence.get("direct_evidence_layer"),
                "local_rank_zscore_research_preview_verified": direct_evidence.get(
                    "local_rank_zscore_research_preview_verified"
                )
                is True,
                "local_rank_zscore_status": direct_evidence.get("local_rank_zscore_status") or "missing",
                "local_rank_zscore_preview_row_count": int(
                    direct_evidence.get("local_rank_zscore_preview_row_count") or 0
                ),
                "local_rank_zscore_eligible_group_count": int(
                    direct_evidence.get("local_rank_zscore_eligible_group_count") or 0
                ),
                "local_rank_zscore_usable_row_count": int(direct_evidence.get("local_rank_zscore_usable_row_count") or 0),
                "worker_batch_research_receipt_ready": direct_evidence.get("worker_batch_research_receipt_ready")
                is True,
                "worker_batch_research_receipt_is_not_worker_execution": direct_evidence.get(
                    "worker_batch_research_receipt_is_not_worker_execution"
                )
                is True,
                "production_blocker_count": effective_pending_count,
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
                "evidence_boundary": direct_evidence.get("evidence_boundary")
                or "observed_local_static_factor_universe_stage_scope_not_production_completion",
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
        direct_evidence = _latest_storage_direct_execution_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        storage_status = (
            "observed_storage_direct_execution_evidence_production_pending"
            if direct_evidence_count
            else "observed_in_storage_static_contract"
        )
        rows.append(
            {
                "id": "LTG-05",
                "goal": "Storage / DuckDB / Parquet 生产化",
                "stage_scope_manifest": "storage_physical_migration_stage_scope_manifest",
                "status": storage_status if stage_rows else "missing_from_storage_static_contract",
                "observed_source": "scripts/storage_contract._physical_migration_stage_scope_rows local static contract + storage SQLite direct evidence",
                "cache_status": "storage_static_contract_plus_direct_evidence"
                if direct_evidence_count
                else "storage_static_contract",
                "cache_mode": "local_static_contract_plus_storage_direct_evidence"
                if direct_evidence_count
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "production_blocker_count": observed_pending_count,
                "physical_schema_validation_done": direct_evidence.get("physical_schema_validation_done") is True,
                "physical_schema_validation_done_count": int(
                    direct_evidence.get("physical_schema_validation_done_count") or 0
                ),
                "schema_validation_acceptance_evidence_status": direct_evidence.get(
                    "schema_validation_acceptance_evidence_status"
                )
                or "",
                "schema_migration_executed": direct_evidence.get("schema_migration_executed") is True,
                "schema_migration_execution_status": direct_evidence.get("schema_migration_execution_status") or "",
                "schema_migration_executed_count": int(direct_evidence.get("schema_migration_executed_count") or 0),
                "schema_migration_dataset_count": int(direct_evidence.get("schema_migration_dataset_count") or 0),
                "schema_migration_noop_verified_count": int(
                    direct_evidence.get("schema_migration_noop_verified_count") or 0
                ),
                "schema_migration_rewrite_executed": direct_evidence.get("schema_migration_rewrite_executed") is True,
                "dataset_version_manifest_validated": direct_evidence.get(
                    "dataset_version_manifest_validated"
                )
                is True,
                "dataset_version_manifest_validate_packet_status": direct_evidence.get(
                    "dataset_version_manifest_validate_packet_status"
                )
                or "",
                "dataset_version_manifest_validated_count": int(
                    direct_evidence.get("dataset_version_manifest_validated_count") or 0
                ),
                "manifest_exists": direct_evidence.get("manifest_exists") is True,
                "duckdb_read_validation_done": direct_evidence.get("duckdb_read_validation_done") is True,
                "duckdb_read_validation_status": direct_evidence.get("duckdb_read_validation_status") or "",
                "duckdb_read_validation_dataset_count": int(
                    direct_evidence.get("duckdb_read_validation_dataset_count") or 0
                ),
                "duckdb_read_validation_contract_ready_count": int(
                    direct_evidence.get("duckdb_read_validation_contract_ready_count") or 0
                ),
                "duckdb_read_validation_ready_dataset_count": int(
                    direct_evidence.get("duckdb_read_validation_ready_dataset_count") or 0
                ),
                "partition_migration_metadata_validation_done": direct_evidence.get(
                    "partition_migration_metadata_validation_done"
                )
                is True,
                "partition_migration_metadata_validation_status": direct_evidence.get(
                    "partition_migration_metadata_validation_status"
                )
                or "",
                "partition_migration_metadata_validated_count": int(
                    direct_evidence.get("partition_migration_metadata_validated_count") or 0
                ),
                "partition_migration_dataset_count": int(
                    direct_evidence.get("partition_migration_dataset_count") or 0
                ),
                "physical_compaction_metadata_validation_done": direct_evidence.get(
                    "physical_compaction_metadata_validation_done"
                )
                is True,
                "physical_compaction_metadata_validation_status": direct_evidence.get(
                    "physical_compaction_metadata_validation_status"
                )
                or "",
                "physical_compaction_metadata_validated_count": int(
                    direct_evidence.get("physical_compaction_metadata_validated_count") or 0
                ),
                "physical_compaction_dataset_count": int(
                    direct_evidence.get("physical_compaction_dataset_count") or 0
                ),
                "physical_compaction_not_needed_count": int(
                    direct_evidence.get("physical_compaction_not_needed_count") or 0
                ),
                "cache_ttl_refresh_metadata_validation_done": direct_evidence.get(
                    "cache_ttl_refresh_metadata_validation_done"
                )
                is True,
                "cache_ttl_refresh_metadata_validation_status": direct_evidence.get(
                    "cache_ttl_refresh_metadata_validation_status"
                )
                or "",
                "cache_ttl_refresh_recommended_count": int(
                    direct_evidence.get("cache_ttl_refresh_recommended_count") or 0
                ),
                "cache_ttl_dataset_count": int(direct_evidence.get("cache_ttl_dataset_count") or 0),
                "cache_ttl_refresh_executed_count": int(
                    direct_evidence.get("cache_ttl_refresh_executed_count") or 0
                ),
                "artifact_cleanup_review_done": direct_evidence.get("artifact_cleanup_review_done") is True,
                "artifact_cleanup_review_status": direct_evidence.get("artifact_cleanup_review_status") or "",
                "artifact_cleanup_candidate_count": int(
                    direct_evidence.get("artifact_cleanup_candidate_count") or 0
                ),
                "artifact_cleanup_review_required_step_count": int(
                    direct_evidence.get("artifact_cleanup_review_required_step_count") or 0
                ),
                "partition_migration_executed": False,
                "physical_compaction_executed": False,
                "cache_ttl_refresh_executed": False,
                "artifact_cleanup_delete_executed": False,
                "storage_physical_execution_request_ready": direct_evidence.get(
                    "storage_physical_execution_request_ready"
                )
                is True,
                "storage_physical_execution_request_status": direct_evidence.get(
                    "storage_physical_execution_request_status"
                )
                or "",
                "storage_direct_evidence_layer": direct_evidence.get("direct_evidence_layer")
                or "L1_static_contract",
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
                "evidence_boundary": "observed_l3_storage_schema_manifest_evidence_not_production_completion"
                if direct_evidence_count
                else "observed_local_static_storage_stage_scope_not_production_completion",
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
                "duckdb_read_validation_done": False,
                "duckdb_read_validation_status": "observation_failed",
                "duckdb_read_validation_dataset_count": 0,
                "duckdb_read_validation_contract_ready_count": 0,
                "duckdb_read_validation_ready_dataset_count": 0,
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
        direct_evidence = _latest_worker_direct_runtime_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        worker_status = (
            "observed_worker_direct_runtime_evidence_production_pending"
            if direct_evidence_count
            else "observed_in_worker_static_contract"
        )
        rows.append(
            {
                "id": "LTG-06",
                "goal": "Worker / Celery / Redis 生产化",
                "stage_scope_manifest": "worker_runtime_evidence_stage_scope_manifest",
                "status": worker_status if stage_rows else "missing_from_worker_static_contract",
                "observed_source": "scripts/worker_contract._worker_runtime_evidence_stage_scope_rows local static contract + worker runtime direct evidence",
                "cache_status": "worker_static_contract_plus_direct_evidence"
                if direct_evidence_count
                else "worker_static_contract",
                "cache_mode": "local_static_contract_plus_worker_direct_evidence"
                if direct_evidence_count
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": list(direct_evidence.get("direct_evidence_stage_keys") or []),
                "production_blocker_count": observed_pending_count,
                "worker_started": False,
                "celery_worker_started": False,
                "redis_pinged": False,
                "scheduler_started": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "healthcheck_executed": direct_evidence.get("synthetic_healthcheck_executed") is True,
                "synthetic_healthcheck_executed": direct_evidence.get("synthetic_healthcheck_executed") is True,
                "local_task_round_trip_verified": direct_evidence.get("local_task_round_trip_verified") is True,
                "task_log_round_trip_verified": direct_evidence.get("task_log_round_trip_verified") is True,
                "task_readback_hash_matches": direct_evidence.get("task_readback_hash_matches") is True,
                "runtime_qa_execution_request_ready": direct_evidence.get(
                    "runtime_qa_execution_request_ready"
                )
                is True,
                "runtime_qa_dry_run_ready": direct_evidence.get("runtime_qa_dry_run_ready") is True,
                "scheduler_default_off_runtime_verified": direct_evidence.get(
                    "scheduler_default_off_runtime_verified"
                )
                is True,
                "provider_model_no_autoschedule_boundary_verified": direct_evidence.get(
                    "provider_model_no_autoschedule_boundary_verified"
                )
                is True,
                "no_trade_no_action_boundary_verified": direct_evidence.get(
                    "no_trade_no_action_boundary_verified"
                )
                is True,
                "runtime_qa_executed": direct_evidence.get("runtime_qa_execution_done") is True,
                "local_fallback_round_trip_verified": direct_evidence.get(
                    "local_fallback_round_trip_verified"
                )
                is True,
                "task_log_persistence_verified": direct_evidence.get("task_log_persistence_verified")
                is True,
                "local_task_control_metadata_verified": direct_evidence.get(
                    "local_task_control_metadata_verified"
                )
                is True,
                "append_only_worker_log_verified": direct_evidence.get("append_only_worker_log_verified")
                is True,
                "cross_process_task_control_verified": direct_evidence.get(
                    "cross_process_task_control_verified"
                )
                is True,
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
                "worker_direct_evidence_layer": direct_evidence.get("direct_evidence_layer")
                or "L1_static_contract",
                "evidence_boundary": "observed_l3_worker_runtime_safety_evidence_not_production_completion"
                if direct_evidence_count
                else "observed_local_static_worker_runtime_stage_scope_not_production_completion",
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
        legacy_retirement_review = candidate_packet.get("candidate_radar_legacy_retirement_review_receipt")
        legacy_retirement_review = legacy_retirement_review if isinstance(legacy_retirement_review, dict) else {}
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
        manifest_direct_evidence_count = int(
            manifest.get("direct_evidence_stage_count")
            or counts.get("candidate_radar_production_stage_scope_direct_evidence_count")
            or 0
        )
        direct_evidence = _latest_candidate_radar_direct_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        observed_pending_count = (
            pending_count if manifest_direct_evidence_count else max(pending_count - direct_evidence_count, 0)
        )
        candidate_status = (
            "observed_candidate_radar_direct_evidence_production_pending"
            if direct_evidence_count
            else "observed_in_candidate_radar_cache"
        )
        rows.append(
            {
                "id": "LTG-13",
                "goal": "下一票雷达快扫生产化",
                "stage_scope_manifest": "candidate_radar_production_stage_scope_manifest",
                "status": candidate_status if manifest_visible else "missing_from_candidate_radar_cache",
                "observed_source": "GET /api/candidate-radar/cache local builder + candidate radar direct evidence",
                "cache_status": str(candidate_packet.get("status") or "missing"),
                "cache_mode": "cache_only_plus_candidate_radar_direct_evidence"
                if direct_evidence_count
                else str(candidate_packet.get("mode") or "cache_only"),
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": list(direct_evidence.get("direct_evidence_stage_keys") or []),
                "production_blocker_count": observed_pending_count,
                "production_radar_replacement_complete": manifest.get("production_radar_replacement_complete") is True,
                "legacy_retirement_ready": manifest.get("legacy_retirement_ready") is True,
                "full_pool_scan_done": manifest.get("full_pool_scan_done") is True,
                "deep_scan_done": manifest.get("deep_scan_done") is True,
                "provider_backed_acceptance_done": manifest.get("provider_backed_acceptance_done") is True,
                "worker_backed_execution_done": manifest.get("worker_backed_execution_done") is True,
                "browser_visual_delta_qa_done": (
                    direct_evidence.get("browser_visual_delta_qa_done") is True
                    or manifest.get("browser_visual_delta_qa_done") is True
                ),
                "cache_render_boundary_verified": direct_evidence.get("cache_render_boundary_verified") is True,
                "quick_scan_task_pipeline_verified": (
                    direct_evidence.get("quick_scan_task_pipeline_verified") is True
                ),
                "local_full_pool_execution_receipt_verified": (
                    direct_evidence.get("local_full_pool_execution_receipt_verified") is True
                ),
                "local_deep_scan_review_receipt_verified": (
                    direct_evidence.get("local_deep_scan_review_receipt_verified") is True
                ),
                "worker_full_pool_fallback_execution_verified": (
                    direct_evidence.get("worker_full_pool_fallback_execution_verified") is True
                ),
                "worker_deep_scan_fallback_execution_verified": (
                    direct_evidence.get("worker_deep_scan_fallback_execution_verified") is True
                ),
                "browser_visual_performance_evidence_verified": (
                    direct_evidence.get("browser_visual_performance_evidence_verified") is True
                ),
                "production_replacement_review_ready": (
                    direct_evidence.get("production_replacement_review_ready") is True
                ),
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
                "legacy_retirement_review_visible": bool(legacy_retirement_review),
                "legacy_retirement_review_status": str(legacy_retirement_review.get("status") or "missing"),
                "legacy_retirement_review_route": str(
                    legacy_retirement_review.get("route") or "POST /api/candidate-radar/legacy-retirement-review"
                ),
                "legacy_retirement_review_explicit_task_done": (
                    legacy_retirement_review.get("explicit_legacy_retirement_review_done") is True
                ),
                "legacy_retirement_review_ready_for_local_review": (
                    legacy_retirement_review.get("local_review_ready") is True
                ),
                "legacy_retirement_review_direct_evidence_verified": (
                    direct_evidence.get("legacy_retirement_review_direct_evidence_verified") is True
                ),
                "legacy_retirement_review_production_blocker_count": int(
                    legacy_retirement_review.get("production_blocker_count")
                    or counts.get("candidate_radar_legacy_retirement_review_production_blocker_count")
                    or 0
                ),
                "legacy_retirement_review_can_close_goal": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "candidate_direct_evidence_layer": direct_evidence.get("direct_evidence_layer")
                or "L1_static_contract",
                "evidence_boundary": "observed_l3_candidate_radar_local_direct_evidence_not_production_replacement"
                if direct_evidence_count
                else "observed_local_cache_stage_scope_manifest_not_production_completion",
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
                "legacy_retirement_review_visible": False,
                "legacy_retirement_review_status": "observation_failed",
                "legacy_retirement_review_route": "POST /api/candidate-radar/legacy-retirement-review",
                "legacy_retirement_review_explicit_task_done": False,
                "legacy_retirement_review_ready_for_local_review": False,
                "legacy_retirement_review_direct_evidence_verified": False,
                "legacy_retirement_review_production_blocker_count": 0,
                "legacy_retirement_review_can_close_goal": False,
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
            and (
                row.get("exact_payload_contract_ready") is True
                or row.get("interaction_contract_ready") is True
                or row.get("local_contract_ready") is True
            )
        )
        direct_evidence = _latest_next_session_direct_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        observed_pending_count = pending_count
        next_session_status = (
            "observed_next_session_browser_direct_evidence_production_pending"
            if direct_evidence_count
            else "observed_in_next_session_map_static_contract"
        )
        rows.append(
            {
                "id": "LTG-08",
                "goal": "ECharts 次日操作图谱成熟版",
                "stage_scope_manifest": "next_session_production_replacement_stage_scope_manifest",
                "status": next_session_status if stage_rows else "missing_from_next_session_map_static_contract",
                "observed_source": (
                    "scripts/next_session_map_contract.build_contract local static contract + next-session browser QA direct evidence"
                ),
                "cache_status": str(next_session_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract_plus_next_session_browser_direct_evidence"
                if direct_evidence_count
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": list(direct_evidence.get("direct_evidence_stage_keys") or []),
                "production_blocker_count": observed_pending_count,
                "production_replacement_complete": next_session_contract.get("production_replacement_complete") is True,
                "streamlit_parity_complete": next_session_contract.get("streamlit_parity_complete") is True,
                "browser_visual_qa_done": direct_evidence.get("browser_visual_qa_done") is True,
                "browser_performance_trace_done": direct_evidence.get("browser_performance_trace_done") is True,
                "reduced_motion_accessibility_qa_done": (
                    direct_evidence.get("reduced_motion_accessibility_qa_done") is True
                ),
                "local_browser_qa_review_ready": direct_evidence.get("local_browser_qa_review_ready") is True,
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
                "next_session_direct_evidence_layer": direct_evidence.get("direct_evidence_layer")
                or "L1_static_contract",
                "evidence_boundary": "observed_l3_next_session_browser_evidence_not_production_replacement"
                if direct_evidence_count
                else "observed_local_static_next_session_stage_scope_not_production_completion",
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
        direct_evidence = _latest_tauri_package_direct_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        tauri_status = (
            "observed_tauri_release_binary_direct_evidence_production_pending"
            if direct_evidence_count
            else "observed_in_tauri_desktop_static_contract"
        )
        rows.append(
            {
                "id": "LTG-09",
                "goal": "Tauri desktop production package",
                "stage_scope_manifest": "tauri_production_package_stage_scope_manifest",
                "status": tauri_status if stage_rows else "missing_from_tauri_desktop_static_contract",
                "observed_source": (
                    "scripts/tauri_desktop_contract.build_contract local static contract + tauri release binary artifact direct evidence"
                ),
                "cache_status": str(tauri_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract_plus_tauri_release_binary_artifact_evidence"
                if direct_evidence_count
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": list(direct_evidence.get("direct_evidence_stage_keys") or []),
                "production_blocker_count": observed_pending_count,
                "production_package_complete": tauri_contract.get("production_package_complete") is True,
                "tauri_build_executed": tauri_contract.get("tauri_build_executed") is True,
                "packaged_runtime_qa_done": tauri_contract.get("packaged_runtime_qa_done") is True,
                "tauri_package_durable_evidence_complete": tauri_contract.get(
                    "tauri_package_durable_evidence_complete"
                )
                is True,
                "release_binary_artifact_qa_done": direct_evidence.get("release_binary_artifact_qa_done") is True,
                "release_binary_artifact_review_ready": direct_evidence.get(
                    "release_binary_artifact_qa_done"
                )
                is True,
                "tauri_build_repeatability_done": direct_evidence.get("tauri_build_repeatability_done") is True,
                "app_bundle_artifact_qa_done": direct_evidence.get("app_bundle_artifact_qa_done") is True,
                "dmg_distribution_artifact_qa_done": direct_evidence.get("dmg_distribution_artifact_qa_done") is True,
                "packaged_app_launch_smoke_done": direct_evidence.get("packaged_app_launch_smoke_done") is True,
                "packaged_app_launch_qa_done": direct_evidence.get("packaged_app_launch_qa_done") is True,
                "backend_offline_packaged_ux_verified": direct_evidence.get(
                    "backend_offline_packaged_ux_verified"
                )
                is True,
                "backend_offline_packaged_ux_screenshot_sha256": direct_evidence.get(
                    "backend_offline_packaged_ux_screenshot_sha256"
                )
                or "",
                "backend_offline_packaged_ux_observed_route": direct_evidence.get(
                    "backend_offline_packaged_ux_observed_route"
                )
                or "",
                "backend_startup_runtime_validated": direct_evidence.get(
                    "backend_startup_runtime_validated"
                )
                is True,
                "backend_startup_runtime_screenshot_sha256": direct_evidence.get(
                    "backend_startup_runtime_screenshot_sha256"
                )
                or "",
                "backend_startup_api_base_observed": direct_evidence.get(
                    "backend_startup_api_base_observed"
                )
                or "",
                "backend_startup_health_status_observed": direct_evidence.get(
                    "backend_startup_health_status_observed"
                )
                or "",
                "config_log_runtime_paths_validated": direct_evidence.get(
                    "config_log_runtime_paths_validated"
                )
                is True,
                "config_log_runtime_screenshot_sha256": direct_evidence.get(
                    "config_log_runtime_screenshot_sha256"
                )
                or "",
                "config_file_policy_observed": direct_evidence.get("config_file_policy_observed") or "",
                "log_file_policy_observed": direct_evidence.get("log_file_policy_observed") or "",
                "direct_gap_evidence_stage_count": direct_evidence.get(
                    "direct_gap_evidence_stage_count"
                )
                or 0,
                "direct_gap_evidence_stage_keys": list(
                    direct_evidence.get("direct_gap_evidence_stage_keys") or []
                ),
                "signing_notarization_review_ready": direct_evidence.get(
                    "signing_notarization_review_ready"
                )
                is True,
                "signing_notarization_review_status": direct_evidence.get(
                    "signing_notarization_review_status"
                )
                or "",
                "codesign_signature_type": direct_evidence.get("codesign_signature_type") or "",
                "codesign_team_identifier_status": direct_evidence.get(
                    "codesign_team_identifier_status"
                )
                or "",
                "spctl_assessment_status": direct_evidence.get("spctl_assessment_status") or "",
                "spctl_message_safe": direct_evidence.get("spctl_message_safe") or "",
                "temporary_dmg_detected": direct_evidence.get("temporary_dmg_detected") is True,
                "temporary_dmg_ignored_for_distribution": direct_evidence.get(
                    "temporary_dmg_ignored_for_distribution"
                )
                is True,
                "production_signing_notarization_ready": direct_evidence.get(
                    "production_signing_notarization_ready"
                )
                is True,
                "tauri_build_command_reviewed_safe": direct_evidence.get("build_command_reviewed_safe") or "",
                "tauri_launch_command_reviewed_safe": direct_evidence.get("launch_command_reviewed_safe") or "",
                "tauri_launch_observed_process_name": direct_evidence.get("observed_process_name") or "",
                "release_binary_artifact_path": direct_evidence.get("release_binary_path") or "",
                "release_binary_artifact_size_bytes": direct_evidence.get("release_binary_size_bytes") or 0,
                "release_binary_artifact_modified_at": direct_evidence.get("release_binary_modified_at") or "",
                "app_bundle_artifact_path": direct_evidence.get("app_bundle_path") or "",
                "dmg_distribution_artifact_path": direct_evidence.get("dmg_distribution_path") or "",
                "temporary_dmg_count": direct_evidence.get("temporary_dmg_count") or 0,
                "temporary_dmg_ignored_for_distribution": direct_evidence.get(
                    "temporary_dmg_ignored_for_distribution"
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
                "app_bundle_detected": direct_evidence.get("app_bundle_detected") is True,
                "dmg_distribution_detected": direct_evidence.get("dmg_distribution_detected") is True,
                "signing_notarization_done": direct_evidence.get("signing_notarization_done") is True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "tauri_direct_evidence_layer": direct_evidence.get("direct_evidence_layer") or "L1_static_contract",
                "evidence_boundary": "observed_l3_tauri_package_artifact_not_packaged_runtime_or_production_package"
                if direct_evidence_count
                else "observed_local_static_tauri_stage_scope_not_production_completion",
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
        from server.services import legacy_service
        from scripts import streamlit_legacy_contract

        streamlit_contract = streamlit_legacy_contract.build_contract()
        if not isinstance(streamlit_contract, dict):
            streamlit_contract = {}
        legacy_packet = legacy_service.read_legacy_bridge_cache()
        parity_review = legacy_packet.get("streamlit_ordinary_workflow_parity_review")
        parity_review = parity_review if isinstance(parity_review, dict) else {}
        parity_review_ready = parity_review.get("local_review_ready") is True
        parity_direct_evidence_verified = parity_review.get("direct_evidence_verified") is True
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
        direct_evidence_count = 1 if parity_direct_evidence_verified else 0
        direct_evidence_stage_keys = (
            ["ordinary_workflow_replacement_parity"] if parity_direct_evidence_verified else []
        )
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        rows.append(
            {
                "id": "LTG-10",
                "goal": "Streamlit 完全退出普通主流程",
                "stage_scope_manifest": "streamlit_retirement_stage_scope_manifest",
                "status": "observed_streamlit_direct_parity_evidence_retirement_pending"
                if parity_direct_evidence_verified
                else "observed_in_streamlit_legacy_static_contract"
                if stage_rows
                else "missing_from_streamlit_legacy_static_contract",
                "observed_source": "POST /api/legacy/ordinary-workflow-parity-review local direct evidence"
                if parity_direct_evidence_verified
                else "scripts/streamlit_legacy_contract.build_contract local static contract",
                "cache_status": str(streamlit_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract_plus_streamlit_parity_direct_evidence"
                if parity_direct_evidence_verified
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_count": direct_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence_stage_keys,
                "production_blocker_count": observed_pending_count,
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
                "streamlit_ordinary_workflow_parity_review_ready": parity_review_ready,
                "streamlit_ordinary_workflow_parity_review_status": str(
                    parity_review.get("status") or "missing"
                ),
                "streamlit_ordinary_workflow_parity_direct_evidence_verified": parity_direct_evidence_verified,
                "streamlit_ordinary_workflow_parity_review_is_not_retirement": True,
                "ordinary_fallback_dependency_count": int(
                    parity_review.get("ordinary_fallback_dependency_count") or 0
                ),
                "full_streamlit_removal_blocker_count": int(
                    parity_review.get("full_streamlit_removal_blocker_count") or 0
                ),
                "ordinary_blocking_workflows": parity_review.get("ordinary_blocking_workflows") or [],
                "full_removal_blocking_workflows": parity_review.get("full_removal_blocking_workflows")
                or [],
                "replacement_parity_complete": parity_review.get("replacement_parity_complete") is True,
                "candidate_radar_parity_complete": parity_review.get("candidate_radar_parity_complete")
                is True,
                "provider_backed_parity_done": parity_review.get("provider_backed_parity_done") is True,
                "browser_performance_qa_done": parity_review.get("browser_performance_qa_done") is True,
                "admin_debug_retention_decision_done": parity_review.get("admin_debug_retention_decision_done")
                is True,
                "fallback_removed_by_contract": False,
                "app_py_deleted_by_contract": False,
                "streamlit_opened_by_contract": parity_review.get("streamlit_opened_by_review") is True,
                "legacy_tools_run_by_contract": parity_review.get("legacy_tools_run_by_review") is True,
                "tasks_created_by_contract": parity_review.get("tasks_created_by_cache_render") is True,
                "provider_model_task_dispatched_by_contract": parity_review.get(
                    "provider_model_task_dispatched_by_review"
                )
                is True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "observed_l3_streamlit_parity_review_not_retirement_completion"
                if parity_direct_evidence_verified
                else "observed_local_static_streamlit_stage_scope_not_retirement_completion",
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
        local_gate_run_receipt = audit_service._read_local_push_gate_run_receipt()
        push_receipt, _ = audit_service._release_gate_push_readiness_receipt(
            release_gate,
            ci_triage_contract,
            local_gate_run_receipt,
        )
        push_receipt = push_receipt if isinstance(push_receipt, dict) else {}
        stage_rows = audit_service._release_gate_stage_scope_rows(
            release_gate,
            push_receipt,
            ci_triage_contract,
            local_gate_run_receipt,
        )
        stage_rows = stage_rows if isinstance(stage_rows, list) else []
        direct_evidence = _latest_release_gate_direct_evidence_summary()
        direct_evidence_count = int(direct_evidence.get("direct_evidence_stage_count") or 0)
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
                "status": (
                    "observed_release_gate_direct_evidence_remote_ci_pending"
                    if stage_rows and direct_evidence_count
                    else (
                        "observed_in_audit_cache_release_gate_contract"
                        if stage_rows
                        else "missing_from_audit_cache_release_gate_contract"
                    )
                ),
                "observed_source": (
                    "server.services.audit_service release gate local static helpers + local push gate run receipt "
                    "also surfaced by GET /api/audit/cache"
                ),
                "cache_status": direct_evidence.get("status") or ("ready" if stage_rows else "missing"),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence.get("direct_evidence_stage_keys", []),
                "release_gate_direct_evidence_layer": direct_evidence.get("direct_evidence_layer"),
                "production_blocker_count": pending_count,
                "local_gate_ready": release_gate.get("local_gate_ready") is True,
                "ci_mirror_ready": release_gate.get("ci_mirror_ready") is True,
                "push_readiness_receipt_ready": push_receipt.get("local_receipt_ready") is True,
                "ready_for_explicit_push_sequence": push_receipt.get("ready_for_explicit_local_gate_then_push")
                is True,
                "release_gate_complete": release_gate.get("release_gate_complete") is True,
                "fresh_local_gate_run_observed": direct_evidence.get("fresh_local_gate_run_observed") is True,
                "local_push_gate_receipt_head_matches_current": direct_evidence.get(
                    "local_push_gate_receipt_head_matches_current"
                )
                is True,
                "local_push_gate_receipt_head": direct_evidence.get("local_push_gate_receipt_head") or "",
                "local_push_gate_receipt_current_head": direct_evidence.get("local_push_gate_receipt_current_head")
                or "",
                "local_push_gate_check_count": int(direct_evidence.get("local_push_gate_check_count") or 0),
                "required_local_gate_checks_present": direct_evidence.get("required_local_gate_checks_present")
                is True,
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
                "evidence_boundary": direct_evidence.get("evidence_boundary")
                or "observed_local_release_gate_stage_scope_not_fresh_gate_or_remote_ci_completion",
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
        release_receipt_ready = (
            isolation_contract.get("trade_isolation_release_receipt_ready") is True
            and isolation_contract.get("trade_isolation_release_receipt_status")
            == "trade_isolation_release_receipt_ready_research_release_only"
            and isolation_contract.get("real_trading_connected") is False
            and isolation_contract.get("broker_adapter_connected") is False
            and isolation_contract.get("order_endpoint_present") is False
            and isolation_contract.get("trade_execution_api_enabled") is False
            and isolation_contract.get("external_calls_triggered") is False
            and isolation_contract.get("tushare_called") is False
            and isolation_contract.get("deepseek_called") is False
            and isolation_contract.get("github_called") is False
            and isolation_contract.get("does_not_execute_trades") is True
            and isolation_contract.get("does_not_modify_strategy_action") is True
            and isolation_contract.get("does_not_modify_holdings") is True
            and isolation_contract.get("contains_secret") is False
        )
        direct_evidence_count = 1 if release_receipt_ready else 0
        direct_evidence_stage_keys = (
            ["research_release_trade_isolation_receipt"] if release_receipt_ready else []
        )
        observed_pending_count = max(pending_count - direct_evidence_count, 0)
        rows.append(
            {
                "id": "LTG-12",
                "goal": "真实交易链路继续保持隔离",
                "stage_scope_manifest": "trade_isolation_stage_scope_manifest",
                "status": "observed_trade_isolation_release_direct_evidence_research_only"
                if release_receipt_ready
                else "observed_in_trade_isolation_static_contract"
                if stage_rows
                else "missing_from_trade_isolation_static_contract",
                "observed_source": "scripts/trade_isolation_contract.build_contract local static contract + research release isolation receipt"
                if release_receipt_ready
                else "scripts/trade_isolation_contract.build_contract local static contract",
                "cache_status": str(isolation_contract.get("status") or "missing"),
                "cache_mode": "local_static_contract_plus_trade_isolation_release_receipt"
                if release_receipt_ready
                else "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": observed_pending_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_evidence_stage_keys,
                "production_blocker_count": observed_pending_count,
                "trade_isolation_release_receipt_ready": release_receipt_ready,
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
                "evidence_boundary": "observed_l3_trade_isolation_release_receipt_not_real_trading_approval"
                if release_receipt_ready
                else "observed_local_static_trade_isolation_not_real_trading_integration",
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
        motion_evidence: dict[str, Any] = {}
        motion_review: dict[str, Any] = {}
        try:
            from server.services import audit_service
            from storage.sqlite_meta import SQLiteMetaStore

            audit_packet = SQLiteMetaStore(audit_service.SQLITE_META_PATH).read_packet(
                "command_center_3_call_ledger_audit_cache"
            )
            if isinstance(audit_packet, dict):
                evidence_packet = audit_packet.get("motion_browser_qa_evidence_contract")
                review_packet = audit_packet.get("motion_browser_qa_review_contract")
                motion_evidence = evidence_packet if isinstance(evidence_packet, dict) else {}
                motion_review = review_packet if isinstance(review_packet, dict) else {}
        except Exception:
            motion_evidence = {}
            motion_review = {}
        browser_visual_ready = motion_evidence.get("visual_qa_complete") is True
        browser_performance_ready = motion_evidence.get("browser_performance_verified") is True
        reduced_motion_ready = motion_evidence.get("reduced_motion_passed") is True
        local_review_ready = motion_review.get("local_browser_qa_review_ready") is True
        direct_stage_keys = []
        if browser_visual_ready:
            direct_stage_keys.append("viewport_visual_qa_execution")
        if browser_performance_ready:
            direct_stage_keys.append("browser_performance_trace_execution")
        if reduced_motion_ready:
            direct_stage_keys.append("reduced_motion_accessibility_review")
        if local_review_ready:
            direct_stage_keys.append("local_artifact_review")
        direct_stage_key_set = set(direct_stage_keys)
        local_evidence_count = max(
            local_evidence_count,
            sum(
                1
                for row in stage_rows
                if isinstance(row, dict)
                and (
                    row.get("local_stage_evidence_present") is True
                    or str(row.get("stage_key") or "") in direct_stage_key_set
                )
            ),
        )
        direct_evidence_count = len(direct_stage_keys)
        pending_stage_count = max(row_count - direct_evidence_count, 0) if direct_evidence_count else pending_count
        rows.append(
            {
                "id": "LTG-14",
                "goal": "App 动效与可视化清晰度生产化",
                "stage_scope_manifest": "motion_production_stage_scope_manifest",
                "status": (
                    "observed_motion_browser_qa_direct_evidence_production_pending"
                    if direct_evidence_count
                    else (
                        "observed_in_motion_viewport_static_contract"
                        if stage_rows
                        else "missing_from_motion_viewport_static_contract"
                    )
                ),
                "observed_source": "scripts/motion_viewport_qa_contract.build_contract plus local audit motion_browser_qa_evidence_contract",
                "cache_status": str(
                    motion_review.get("status")
                    or motion_evidence.get("status")
                    or motion_contract.get("status")
                    or "missing"
                ),
                "cache_mode": "local_static_contract",
                "row_count": row_count,
                "pending_stage_count": pending_stage_count,
                "local_evidence_stage_count": local_evidence_count,
                "direct_evidence_stage_count": direct_evidence_count,
                "direct_evidence_stage_keys": direct_stage_keys,
                "production_blocker_count": pending_stage_count,
                "production_motion_complete": motion_contract.get("production_motion_complete") is True,
                "visual_qa_complete": browser_visual_ready,
                "browser_performance_verified": browser_performance_ready,
                "browser_visual_qa_promoted": motion_review.get("browser_visual_qa_promoted") is True,
                "browser_performance_promoted": motion_review.get("browser_performance_promoted") is True,
                "durable_ci_evidence_complete": motion_review.get("ci_evidence_complete") is True,
                "browser_runner_executed_by_contract": int(motion_evidence.get("passing_report_count") or 0) >= 2,
                "local_artifact_reviewed_for_production": local_review_ready,
                "motion_browser_qa_report_count": int(motion_evidence.get("report_count") or 0),
                "motion_browser_qa_passing_report_count": int(motion_evidence.get("passing_report_count") or 0),
                "motion_browser_qa_default_passed": motion_evidence.get("default_motion_passed") is True,
                "motion_browser_qa_reduced_motion_passed": reduced_motion_ready,
                "motion_browser_qa_review_ready": local_review_ready,
                "motion_browser_qa_review_task_id": str(motion_review.get("review_task_id") or ""),
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "can_close_from_observed_row": False,
                "evidence_boundary": "local_browser_visual_performance_artifacts_are_L3_direct_evidence_not_production_motion_completion",
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
            item["observed_stage_scope_direct_evidence_count"] = observed.get("direct_evidence_stage_count", 0)
            item["observed_stage_scope_direct_evidence_keys"] = observed.get("direct_evidence_stage_keys", [])
            item["observed_stage_scope_can_close_goal"] = False
            if str(item.get("id") or "") == "LTG-13":
                item["observed_candidate_direct_evidence_layer"] = observed.get("candidate_direct_evidence_layer")
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
                item["observed_legacy_retirement_review_status"] = observed.get("legacy_retirement_review_status")
                item["observed_legacy_retirement_review_visible"] = observed.get("legacy_retirement_review_visible")
                item["observed_legacy_retirement_review_ready_for_local_review"] = observed.get(
                    "legacy_retirement_review_ready_for_local_review"
                )
                item["observed_legacy_retirement_review_production_blocker_count"] = observed.get(
                    "legacy_retirement_review_production_blocker_count"
                )
                item["observed_legacy_retirement_review_can_close_goal"] = False
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
