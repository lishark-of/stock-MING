# Command Center 3.0 Long-Term Goals

## Current Baseline

stock-MING 已完成 Command Center 3.0 主架构迁移的阶段性底座：
FastAPI + React/Vite/Tauri + task/storage scaffold + ECharts + Factor Quant Hub + Tushare light path + DeepSeek governance 已形成闭环。

但 3.0 尚未完全替代 Streamlit。
当前仍处于“可审计投研客户端迁移阶段”，不是完整生产交易终端。

This document is the long-term development baseline for unfinished Command Center 3.0 work. Future work should update this roadmap instead of redefining the migration direction in each handoff.

## Status Legend

| status | meaning |
|---|---|
| `done_real` | 已完成并通过本地或真实路径跑通。 |
| `scaffold` | 结构、合同或 UI 已有，但不是生产实现。 |
| `preflight` | 只做准备度检查，不启动生产服务。 |
| `mock` | 由测试替身或本地样本验证，不代表真实外部验收。 |
| `sanitizer` | 只验证清洗、白名单和安全写回，不代表模型稳定生产调用。 |
| `matrix` | 能力矩阵或目标域已声明，不代表所有接口真实 verified。 |
| `not_started` | 尚未开始或只在规划中。 |

## Completed And Actually Run

- Command Center 3.0 architecture skeleton.
- React/Vite frontend build and chunk split.
- FastAPI cache/task MVP.
- ECharts next-session operation map initial version.
- Tushare light task real path validation.
- 20 stocks with `daily / daily_basic / moneyflow`, 60 successful calls total.
- Factor runtime values written to Parquet.
- Factor cache test isolation.
- DeepSeek pro one real call and mini-benchmark.
- Streamlit marked as `legacy/admin/debug`.

## Completed But Still Initial / Scaffold / Preflight

- Worker / Task system: local fallback, task lifecycle, retry/cancel/lock/dedupe/logs exist; production Celery/Redis is not enabled.
- Storage / DuckDB / Parquet / SQLite / Redis: dataset contracts and local reads exist; production migration/versioning/compaction is incomplete.
- Factor Test Lab: light research metrics exist; full research validation is incomplete.
- Tushare extended validation matrix: domains are declared and button-gated; not all interfaces have real samples.
- DeepSeek pro automatic explanation governance: sanitizer and prompt preview exist; automatic production calls remain disabled.
- Tauri desktop preflight: dev readiness and a production runtime path/startup contract exist; production package validation is incomplete.
- ECharts next-session map maturity: chart contract exists; interaction parity with legacy Streamlit is incomplete.
- Streamlit legacy closeout: legacy status exists; ordinary workflow is not fully migrated.

## Local Implemented But Not Pushed

The local branch may contain roadmap or LTG implementation commits that are not yet pushed. Treat `git log origin/main..HEAD` as the authoritative list before any push gate.

Current local LTG work must not be treated as shared baseline until tests, build, smoke, safety scans, and user confirmation pass. Do not push without confirmation.

## Long-Term Goals Table

| id | long_term_goal | current_status | target_state | priority | success_criteria |
|---|---|---|---|---|---|
| LTG-01 | A 股交易日历级 freshness 生产化 | `done_real` MVP, still needs production validation | All current evidence is gated by expected trade date | P1 | stale / expired / historical / unknown data cannot enter score, support, evidence preview, or action. |
| LTG-02 | Tushare 全接口生产流水线 | core light path `done_real`; extended APIs `matrix` / `mock` | All selected interfaces run through task pipeline with call ledger | P2 | Each interface has real target samples, safe failure states, and no false verified claims. |
| LTG-03 | Factor Test Lab 完整生产化 | light research metrics `done_real`; production QA contract visible; production research incomplete | Research-grade factor validation for single factors | P3 | IC, Rank IC, ICIR, groups, cost, drawdown, sample split, decay, and neutral IC are auditable and research-only. |
| LTG-04 | Factor 全市场 / 股票池研究 | light mode plus local read-plan and execution readiness audit; batch execution pending | watchlist / custom pool / full pool research pipeline | P3 | Large universe runs in task pipeline without blocking UI or entering strategy action. |
| LTG-05 | Storage / DuckDB / Parquet 生产化 | dataset scaffold and factor_values write path | Versioned, queryable local data layer | P4 | schema/version/TTL/compaction/query services are auditable; data artifacts stay out of git. |
| LTG-06 | Worker / Celery / Redis 生产化 | local task fallback, preflight, blocker audit, and healthcheck QA contract | Production-capable worker orchestration with local fallback | P4 | POST returns task_id, worker runs heavy jobs, Redis absence falls back gracefully, scheduler stays off by default. |
| LTG-07 | DeepSeek pro 稳定解释生产化 | manual governance, sanitizer, and local JSON stability audit; mini-benchmark below production target | Stable manual explanation, optional background auto-after-task | P5 | JSON success rate > 90%, no action leakage, no numeric overwrite, cost predictable. |
| LTG-08 | ECharts 次日操作图谱成熟版 | maturing chart contract with interaction readiness audit; legacy parity pending | React/ECharts replaces Streamlit main next-session visual | P5 | Complete cache display, evidence interactions, no frontend action/price/position mutation. |
| LTG-09 | Tauri desktop production package | dev/preflight with runtime contract and local release artifact detection; packaged runtime QA pending | Production desktop shell for ordinary users | P6 | tauri dev/build pass; backend-offline state is friendly; config/log policy is validated; token/key never enters frontend. |
| LTG-10 | Streamlit 完全退出普通主流程 | `legacy/admin/debug` marked, fallback dependency contract visible, still used for fallback | Streamlit only for debug/admin/fallback | P7 | Ordinary research workflow runs through Command Center 3 desktop. |
| LTG-11 | 测试 / CI / smoke / 安全扫描标准化 | local tests and smoke exist | Repeatable gate for every release candidate | P0/P4 | unittest, frontend build, smoke, diff check, secret scan, and artifact scan are documented and enforced. |
| LTG-12 | 真实交易链路继续保持隔离 | auto trading not connected | Trading remains explicitly out of automatic chains | Always | No automatic order path; strategy action cannot be mutated by research/cache/model/frontend paths. |
| LTG-13 | 下一票雷达快扫生产化 | local fast-scan readiness and no-feature-loss QA contracts exist; full-pool/deep-scan/provider acceptance pending | Fast radar scan in Command Center 3 without feature loss or degraded signal coverage | P3 | Radar runs through task pipeline, preserves legacy signal groups, avoids UI stalls, and reports coverage gaps instead of hiding them. |
| LTG-14 | Command Center 3 动效与可视化清晰度优化 | first motion clarity layer, static readiness audit, and production QA contract exist; browser visual/performance QA pending | Apple keynote-grade clarity and restrained motion that makes state changes easier to see | P8 | Motion is purposeful, performant, accessible, respects reduced-motion, and never obscures data or decisions. |

## LTG-01: A 股交易日历级 Freshness 生产化

### Current Status

- freshness gate MVP exists.
- stale / expired / historical data is blocked from `composite_score`, `support_factors`, and evidence preview.
- Existing tests cover part of premarket, intraday, postmarket, closing auction, non-trading day, provider delay grace, and calendar fallback behavior.
- Data Health now exposes a cache-only freshness acceptance matrix for premarket, intraday, closing auction, post-16:30, weekend/holiday, missing `trade_cal`, provider delay grace, and stale/expired/historical/unknown boundaries.
- Data Health now also exposes a local synthetic long-window sample validation that runs the actual freshness gate across premarket, intraday, closing auction, post-16:30, provider grace, holiday cluster, long-weekend, and missing-today scenarios.
- Data Health now separately validates an existing local `trade_cal` Parquet artifact through the storage/DuckDB cache path: schema columns, date window, open/closed rows, current-date coverage, latest completed trading day, and freshness gate context are visible without refreshing providers.
- Data Health now exposes `current_evidence_freshness_qa_contract`, a local cache-only QA contract that separates current evidence from historical/research samples and keeps stale / expired / historical / unknown / future-unavailable rows out of current decision surfaces.

### Gaps

- Full A-share trading-calendar production acceptance is not complete.
- Needs provider-backed long-window `trade_cal` acceptance evidence beyond the local artifact check.
- Needs holiday, weekend, post-close data availability, and most recent completed trading day acceptance.
- Needs provider-backed acceptance that proves the local artifact was produced and refreshed through the explicit task/storage pipeline, not merely present on disk.
- The acceptance matrix is a contract, the synthetic sample is a fixture, the local Parquet validation is a physical artifact check, and the current-evidence QA contract is a boundary contract; none of them call Tushare on page render.

### Implementation Phases

1. Load and validate a long-window `trade_cal` dataset through the task/storage pipeline.
2. Add expected trade date checks to all current evidence producers.
3. Treat historical sample rows as research-only unless they explicitly match current evidence requirements.
4. Extend tests for holiday clusters, long weekends, missing calendar rows, and provider delay windows.

### Acceptance Criteria

- Premarket `expected_date` equals previous completed trading day.
- After 16:30, `expected_date` equals current trading day when the market is open.
- Weekend and holiday `expected_date` equals most recent completed trading day.
- Missing `trade_cal` falls back safely and emits a warning.
- Failing data does not enter score, support, evidence preview, or action.
- Data Health shows the acceptance matrix without calling Tushare/DeepSeek/GitHub or modifying `strategy action`.
- Data Health shows synthetic long-window sample results separately from real `trade_cal` validation, with `trade_cal_long_window_validation_done=false` until provider-backed acceptance is complete.
- Data Health shows local `trade_cal` Parquet validation separately from the synthetic fixture; when missing or too short, blockers remain visible and production acceptance stays pending.
- Data Health shows `current_evidence_freshness_qa_contract` and rows: current evidence requires expected trade date, data date alignment, freshness state eligibility, historical sample separation, provider-backed acceptance pending state, and decision-surface isolation.

### Forbidden

- Do not silently treat unknown freshness as current evidence.
- Do not let stale / expired / historical rows modify `strategy action`.
- Do not hide fallback calendar state.
- Do not treat synthetic samples, local matrix rows, or local artifact checks as provider-backed production acceptance.

### Recommended Commit Message

```text
Harden A-share trading-calendar freshness production gate
```

## LTG-02: Tushare 全接口生产流水线

### Current Status

- `daily / daily_basic / moneyflow` have been run through the real light path.
- Other interfaces are mostly `matrix`, `button-gated`, `mock`, or capability-state only.
- GET cache APIs do not call Tushare.
- Button-gated Tushare refresh packets now expose `api_acceptance_audit`: a local call-ledger semantic audit that checks required fields, safe terminal states, redacted errors, unselected APIs not being marked verified, and non-Parquet interfaces not claiming physical writes.
- Tushare refresh packets now also expose `provider_acceptance_readiness_audit` and `provider_acceptance_readiness_rows`: a production-readiness blocker audit that keeps full-interface provider acceptance pending until all declared APIs have real non-empty provider samples and all target groups are validated by an explicit production acceptance run.
- Tushare refresh packets now expose `failure_mode_qa_contract`: a local call-ledger classifier for empty/no-record windows, permission denied, parse/invalid-result failures, missing required parameters, safe provider errors, and matrix-only unrequested APIs.

### Gaps

- `trade_cal`.
- `margin_detail`.
- `top_list / top_inst`.
- `stk_limit / limit_list_d / limit_cpt_list`.
- `cyq_perf / cyq_chips`.
- `anns_d / forecast / pledge / holdertrade / share_float / stk_surv`.
- `fina_indicator`.
- Provider-backed all-interface acceptance is still incomplete; `api_acceptance_audit` proves packet semantics, not real provider coverage.
- `provider_acceptance_readiness_audit.status=provider_acceptance_pending` is expected while matrix-only targets, blocked/failed calls, empty samples, missing full selection, or missing provider-backed acceptance evidence remain.
- `failure_mode_qa_contract.status=failure_mode_qa_ready_provider_acceptance_pending` proves failure modes are distinguishable in local call ledger rows; it does not prove real provider coverage or production acceptance.

### Implementation Phases

1. Validate `trade_cal` first because freshness depends on it.
2. Validate market evidence groups one at a time: margin, dragon-tiger, limit/emotion, chip, disclosure, hard risk.
3. Add per-interface request parameter contracts and safe error states.
4. Persist only production-approved datasets; keep other results as validation records until storage contracts are ready.

### Acceptance Criteria

- Every selected interface runs through POST task pipeline only.
- Every interface records `call_ledger`, `row_count`, `data_date`, `local_fetched_at`, `call_status`, and `error_message_safe`.
- Permission denied, no record, empty window, parse failure, missing parameter, and blocked state are distinguishable.
- Unselected APIs never display as `verified`.
- `api_acceptance_audit.status=acceptance_audit_passed` only means call-ledger semantics are safe; `full_interface_acceptance_done` must remain false until all declared APIs are selected and provider-validated.
- `failure_mode_qa_contract` shows observed vs ready-not-observed failure modes without raw provider errors, stack traces, token, or key material.
- `provider_acceptance_readiness_audit.provider_backed_acceptance_done=false` and `production_tushare_pipeline_complete=false` until real provider-backed full-interface acceptance is explicitly proven.
- Tokens are never printed, stored in packets, or exposed to frontend.

### Forbidden

- Do not call Tushare from GET cache or page render.
- Do not mark matrix-only rows as real validation.
- Do not treat `api_acceptance_audit` as proof that provider coverage or production refresh is complete.
- Do not treat `failure_mode_qa_contract` as proof that permission-denied, empty-window, or parse-failure cases have all been observed against real Tushare.
- Do not treat `provider_acceptance_readiness_audit` as production completion while it reports `provider_acceptance_pending`.
- Do not commit fetched data artifacts.

### Recommended Commit Message

```text
Validate extended Tushare refresh task pipeline
```

## LTG-03: Factor Test Lab 完整生产化

### Current Status

- IC, Rank IC, ICIR, group return, Top-Bottom, max drawdown, industry/market-cap neutral IC, sample split stability, decay, and cost model exist in light form.
- Current usage is research-only.
- Factor Test Lab now exposes a research-state acceptance contract for `research_pass`, `watchlist`, `disabled`, `invalid`, and `not_enough_data`.
- React displays the state contract and explicitly marks `research_pass` as a research label, not a trade signal.
- GET factor cache now attaches a read-only `factor_values` DuckDB query consumption contract for Factor Test Lab: typed projection, query result contract, cursor page info, and local query lineage are visible without computing production IC metrics from the query rows.
- Factor Test Lab packets now expose `small_pool_acceptance`: a local light-observation readiness audit for IC / Rank IC / ICIR, group return, cost, drawdown, neutral IC, sample split/decay, and PIT/lookahead/survivorship checks. This audit does not treat storage query rows as metric samples and does not prove real small-pool or full-market production validation.
- Factor Test Lab packets now expose `production_validation_qa_contract`: a local QA contract for future provider-backed small-pool validation, multi-horizon forward returns, rolling IC/ICIR, out-of-sample decay, production cost assumptions, neutralization stability, PIT/lookahead/survivorship controls, storage-query boundaries, research-only state transitions, and trade/action isolation. It does not run provider-backed samples, full-market research, external calls, or trade actions.

### Gaps

- No complete full-market or stock-pool validation.
- Multi-window, multi-horizon, out-of-sample, and factor decay validation are incomplete.
- Production-grade transaction cost assumptions are not validated.
- Industry and market-cap neutral stability needs larger samples.
- The research-state contract and DuckDB query consumption contract are local/light-mode governance and do not prove full-market validation.
- The small-pool acceptance audit is a local readiness contract; provider-backed small-pool samples are still pending.
- The production validation QA contract is visible, but all provider-backed / full-market production validation remains pending.

### Implementation Phases

1. Stabilize single-factor research metrics on small real pools.
2. Add multiple forward-return horizons and rolling windows.
3. Add production cost assumptions and turnover diagnostics.
4. Add factor state transitions: `research_pass`, `watchlist`, `disabled`, `invalid`, `not_enough_data`.
5. Keep `production_validation_qa_contract` current until provider-backed validation tasks can prove completion.

### Acceptance Criteria

- Single factor has IC, Rank IC, and ICIR.
- Group returns and Top-Bottom are present.
- Turnover and cost-adjusted return are present.
- Out-of-sample and recent decay are present.
- Results never enter `strategy action`.
- All result states remain research-only and do not enter `core_action`, `evidence_effects`, `next_session_projection`, or frontend-computed action.
- DuckDB query consumption remains local/read-only, does not write Parquet on GET, does not call providers, and does not convert query rows into trade signals or production IC acceptance.
- `small_pool_acceptance.status=local_small_pool_acceptance_ready` only means local light observations satisfy the readiness checklist; `real_small_pool_validation_done` and `full_market_validation_done` must remain false until provider-backed samples are validated.
- `production_validation_qa_contract.production_factor_test_validation_complete=false` until provider-backed small-pool samples, multi-horizon/rolling-window validation, cost assumptions, neutralization stability, bias controls, and trade/action isolation are all verified.

### Forbidden

- Do not present research metrics as trading advice.
- Do not promote `research_pass` to action without separate approval.
- Do not compute action in frontend.
- Do not treat storage query consumption as real small-pool, full-market, or production factor validation.
- Do not treat local small-pool readiness as real provider-backed production validation.
- Do not treat `production_validation_qa_contract` as execution evidence; it is a QA checklist until future button/task validation proves the rows.

### Recommended Commit Message

```text
Promote Factor Test Lab to research-grade metrics
```

## LTG-04: Factor 全市场 / 股票池研究

### Current Status

- light mode runs.
- Current scope is mainly single stock, position, or watchlist style usage.
- Factor Quant Hub now exposes a universe research contract for `current_target`, `watchlist`, `custom_pool`, and `full_pool`.
- Current implemented compute pipeline remains `current_target` light mode.
- A button-gated local `run_factor_universe_research_plan` task now consumes storage query contracts for `factor_values`, `daily`, `daily_basic`, `moneyflow`, and `trade_cal`, then writes `universe_research_task_plan` back to Factor Quant Hub cache.
- The read-plan task is a worker/task consumption plan, not full-pool research validation.
- Factor Quant Hub now exposes `universe_execution_readiness_audit` and `universe_execution_readiness_rows`, summarizing read-plan readiness, storage query contract consumption, worker batch execution, cross-sectional rank/zscore, neutralization, full-pool validation, frontend read-only boundaries, partial-pool boundaries, and trade isolation.

### Gaps

- Full-market universe is incomplete.
- Industry and market-cap neutral full-sample validation is incomplete.
- Factor combination research is incomplete.
- The universe read plan does not perform watchlist/custom/full-pool batch research yet.
- Cross-sectional rank, zscore, neutralization, result summaries, and worker-backed large-universe execution are still incomplete.
- `universe_execution_readiness_audit.status=read_plan_ready_execution_pending` only proves the local read-plan contract after the button task; it is not provider-backed full-market research and keeps production blockers visible.

### Implementation Phases

1. Define `watchlist`, `custom_pool`, and `full_pool` universe contracts.
2. Add batch execution through task pipeline.
3. Add cross-sectional rank, zscore, neutralization, and result summaries.
4. Keep UI as progress/result display only.

### Acceptance Criteria

- Large universe runs through pipeline.
- React displays progress and final results only.
- Heavy calculation does not run in frontend or Streamlit synchronous path.
- Research outputs remain outside `strategy action`.
- Partial pools are explicitly not full-market proof, and page render does not start full-pool research.
- Storage query read plans remain local metadata contracts until real research execution and full-pool validation are complete.
- `universe_execution_readiness_audit.production_factor_universe_complete=false` until worker-backed batch execution, rank/zscore, neutralization, result summaries, and full-pool/provider-backed validation are implemented and verified.

### Forbidden

- Do not block page render with full-pool computation.
- Do not write universe data to git.
- Do not treat partial universe samples as full-market proof.
- Do not treat `universe_execution_readiness_audit` as production factor-universe completion while it reports execution pending.

### Recommended Commit Message

```text
Add factor universe research pipeline
```

## LTG-05: Storage / DuckDB / Parquet 生产化

### Current Status

- SQLite / Parquet / DuckDB / Redis scaffold exists.
- `factor_values` has a Parquet write path.
- `trade_cal` is declared as a dataset.
- Schema validation and partition writer scaffold exist.
- Storage overview now exposes path-only local artifact hygiene for `.stock_ming_3`, legacy cache, frontend build output, Node dependencies, Tauri target output, and Python bytecode cache boundaries.
- The artifact hygiene audit is `manual_only_no_delete_on_get`: it reports generated/data artifact boundaries but does not delete files, read payloads, scan secret values, refresh providers, or touch `strategy action`.
- `POST /api/storage/artifact-hygiene/dry-run` now creates a local task and dry-run packet that lists cleanup candidates without deleting files, reading payloads, scanning secret values, or calling external providers.
- Storage overview and catalog now expose a metadata-only schema migration preflight for all canonical datasets: target schema version, required columns, primary key, partition expectation, current parquet status, and manual migration boundaries are visible without reading payloads or writing Parquet.
- Storage overview and catalog now expose a cache-only dataset version policy matrix: declared dataset version, manifest path, physical validation boundary, and no-write-on-GET guarantees are visible before any production manifest writer exists.
- `POST /api/storage/schema-validation/dry-run` now creates a local task and packet that reads Parquet schema metadata only, compares physical columns with canonical schema contracts, and reports `schema_validated` / `schema_mismatch` / `missing_dataset` before any migration.
- `POST /api/storage/partition-migration/dry-run` now creates a local task and packet that builds per-dataset partition migration plans from schema validation and partition contracts, without reading row payloads or writing partitioned Parquet.
- `POST /api/storage/compaction/dry-run` now creates a local task and packet that lists Parquet compaction ready/not-needed/missing rows without reading row payloads or rewriting Parquet.
- `POST /api/storage/cache-ttl/dry-run` now creates a local task and packet that lists fresh/stale/missing TTL states and refresh recommendations without refreshing providers or writing Parquet.
- DuckDB query service policy is visible in storage overview/catalog: canonical dataset paths, supported filters, limit guard, safe parameter binding, and frontend no-direct-DataFrame boundaries are auditable.
- DuckDB dataset reads now return typed projection columns, `duckdb_query_result_contract.v1`, and offset cursor `page_info` for local Parquet reads.
- React Storage now exposes read-only DuckDB cursor controls that pass `page_info.next_cursor` back through FastAPI GET storage APIs; the controls do not refresh providers, write Parquet, or read DataFrames directly.
- React Storage now exposes read-only dataset filters for `limit`, `ts_code`, `trade_date`, `start_date`, and `end_date`; applying filters resets to the first page and still routes only through GET storage APIs.
- Factor Universe now has a button-gated local read-plan task that consumes storage query contracts and records dataset-level projection/page metadata for future worker consumption.
- Storage overview/catalog now expose `storage_production_blocker_audit`: production remains `storage_production_blocked` until physical schema validation, schema migration, dataset version manifest validation, partition migration, physical compaction, and TTL refresh execution are separately implemented.

### Gaps

- Production schema migration execution.
- Physical dataset version manifest writing and validation beyond the read-only version policy matrix.
- Physical partition migration execution.
- Physical compaction execution beyond the button-gated dry-run.
- Physical refresh scheduling/execution beyond the button-gated cache TTL dry-run.
- Real large-universe research execution beyond the local Factor Universe read plan.
- Full-pool research consumption, richer query result contract hardening beyond the current local DuckDB read path, and production-grade query ergonomics beyond the current basic UI filters.
- Reviewed manual cleanup workflow after dry-run.

### Implementation Phases

1. Define dataset schema versions and migration policy.
2. Promote partition strategy per dataset.
3. Add DuckDB query service wrappers for UI/API use.
4. Add compaction and cleanup preflight.
5. Keep cache-only APIs strictly read-only.

### Acceptance Criteria

- packets / tasks / factor_values / trade_cal / market data have clear storage policies.
- UI does not directly read large DataFrames.
- Queries go through DuckDB/service.
- Data files do not enter git.
- Schema migration preflight remains visibly `preflight_ready`, with `physical_validation_done_count=0` and `migration_executed_count=0` until explicit future tasks prove otherwise.
- Dataset version policy remains visibly `policy_ready`, but `physical_dataset_version_validated_count=0` and `dataset_version_migration_executed_count=0` until explicit future manifest/validation tasks prove otherwise.
- Schema validation dry-run is button-gated, reads no row payload, writes no Parquet, and records missing/mismatch/validated rows before any migration.
- Partition migration dry-run is button-gated, writes no partitioned Parquet, and records ready/blocked/missing rows before any partition writer task.
- Compaction dry-run is button-gated, writes no Parquet, reads no row payload, and records ready/not-needed/missing rows before any physical compaction task.
- Cache TTL dry-run is button-gated, calls no providers, writes no Parquet, and records fresh/stale/missing refresh recommendations before any refresh task.
- DuckDB query service remains local/canonical-path-only, uses safe parameter binding and limit guards, and is visible to React as a policy matrix; React does not query Parquet or hold large DataFrames directly.
- DuckDB query results expose projection columns, missing projection columns, order columns, `page_info`, and `next_cursor`; these remain read-only local contracts and do not refresh data.
- React cursor controls use only GET storage API cursor parameters, can reset to the first page, and preserve the no-provider-refresh / no-Parquet-write / no-trade-action boundary.
- React dataset filters use only GET storage API query parameters, keep cursor pagination local and read-only, and preserve the no-provider-refresh / no-Parquet-write / no-trade-action boundary.
- Generated artifact hygiene is auditable; dry-run cleanup is button-gated and any real delete/cleanup must remain separate and manually approved.
- Storage overview/catalog now expose `storage_production_blocker_audit` and `storage_production_blocker_rows`, explicitly separating local contracts/dry-runs/preflights from physical production completion.
- Write failure does not pollute packet or action.

### Forbidden

- Do not write Parquet from GET cache.
- Do not treat schema migration preflight as physical validation or production migration completion.
- Do not treat dataset version policy as physical dataset version validation or manifest migration completion.
- Do not treat schema validation dry-run as production schema migration completion.
- Do not treat partition migration dry-run as physical partition migration completion.
- Do not treat compaction dry-run as physical Parquet compaction completion.
- Do not treat cache TTL dry-run as data refresh completion or provider acceptance.
- Do not let frontend bypass the FastAPI + DuckDB query service or run direct Parquet/DataFrame reads.
- Do not treat cursor pagination or typed projection as full-market research execution.
- Do not treat `storage_production_blocked` as a failure of cache safety; it is the expected state until physical schema validation, schema migration, version manifest validation, partition migration, compaction, and TTL refresh execution are separately implemented and verified.
- Do not commit `.parquet`, `.duckdb`, `.sqlite`, `.db`, cache, or generated data.
- Do not hide schema mismatch.

### Recommended Commit Message

```text
Productionize Command Center 3 storage datasets
```

## LTG-06: Worker / Celery / Redis 生产化

### Current Status

- local task fallback, retry, cancel, lock, dedupe, and task logs exist.
- worker preflight exists.
- Worker runtime now exposes a read-only dispatch plan matrix: every task has a future queue, local fallback state, Redis/Celery preconditions, retry/cancel/lock/dedupe/log requirements, and scheduler/external-call boundaries.
- Worker runtime now exposes `worker_production_blocker_audit`: a read-only blocker audit for Redis package/config, Celery package/worker start, stub task migration, queue contracts, button gating, call ledger requirements, scheduler default-off, cache GET no-dispatch, and local-only retry/cancel/lock/dedupe/log controls. It does not start Celery, ping Redis, start APScheduler, or dispatch tasks.
- Worker runtime now exposes `worker_healthcheck_qa_contract`: a static QA matrix for the future explicit production worker healthcheck. It lists Celery process visibility, Redis broker reachability, synthetic task round trip, cross-process retry/cancel, scheduler default-off, provider/model no-autoschedule, task log persistence, external-call boundary, and secret redaction. It does not execute the healthcheck, start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, or execute trades.
- Celery/Redis are not production enabled.

### Gaps

- Real Celery worker.
- Redis broker.
- Task retry execution.
- Task cancellation semantics across worker process.
- Concurrency locks.
- Task log persistence.
- Scheduler production config.

### Implementation Phases

1. Keep local fallback stable.
2. Keep the dispatch plan matrix current as tasks are added, so future Celery/Redis routing has an auditable contract before execution is enabled.
3. Keep `worker_healthcheck_qa_contract` current so the future worker healthcheck has an explicit acceptance checklist before execution is enabled.
4. Add Celery worker execution behind explicit configuration.
5. Add Redis broker configuration and health reporting without cache API pinging Redis.
6. Add retry/cancel/lock behavior for real worker tasks.
7. Keep scheduler default off.

### Acceptance Criteria

- POST task returns `task_id`.
- React polls task status.
- Worker executes heavy tasks.
- Redis absence gracefully falls back or reports clear blocker.
- Worker not started state is visible in UI.
- Production blocker rows are visible in UI, and `production_worker_complete` remains false until a future explicit worker health check proves Celery/Redis startup outside GET cache.
- Worker healthcheck QA rows are visible in UI, and `healthcheck_executed` remains false until a future synthetic/local worker healthcheck is explicitly run.
- Real Tushare/DeepSeek scheduling is never automatic.
- Failures include `error_message_safe`.

### Forbidden

- Do not start Celery, Redis, or scheduler from GET cache.
- Do not auto-schedule real provider/model tasks.
- Do not report preflight as production worker completion.
- Do not report blocker audit as production worker completion.

### Recommended Commit Message

```text
Enable production-ready worker task orchestration
```

## LTG-07: DeepSeek pro 稳定解释生产化

### Current Status

- pro/flash model strategy is configured.
- pro real call succeeded once.
- mini-benchmark ran 8 calls with 75% JSON success.
- sanitizer is effective.
- Factor Quant Hub now exposes a local `deepseek_json_stability_audit` that compares the 75% mini-benchmark baseline with the >90% production target, checks prompt/schema/token-budget/read-only boundaries, and marks automatic production explanation as blocked until larger benchmark and response-format enforcement are proven.
- Current state is suitable for manual explanation, not automatic production calling.

### Gaps

- JSON success rate is not high enough.
- Larger benchmark is missing.
- Response format enforcement is incomplete.
- Token budget strategy is incomplete.
- `auto_after_task` needs conservative production governance.
- `deepseek_json_stability_audit.status=manual_ready_production_blocked` is a local sanitizer/prompt contract, not a real model benchmark pass.

### Implementation Phases

1. Expand benchmark set with representative packets.
2. Tighten response format and retry/repair policy.
3. Track token budget and model choice per purpose.
4. Keep automatic explanation disabled unless explicitly enabled and bounded.
5. Promote `deepseek_json_stability_audit` from local readiness to real benchmark evidence only after provider-backed samples meet the target.

### Acceptance Criteria

- JSON success rate > 90%.
- No illegal fields.
- No trading action leakage.
- No numeric overwrite.
- Token cost is predictable and auditable.
- Failure does not pollute local results.
- `deepseek_json_stability_audit` must show `production_ready=true` only after JSON success rate exceeds 90%, larger benchmark is complete, and response format is enforced.
- GET cache and React render must keep `model_call_status=not_called`.

### Forbidden

- Do not call DeepSeek on page render or GET cache.
- Do not use DeepSeek as a data source.
- Do not let model output overwrite prices, positions, factor values, operation zones, or action.
- Do not treat local sanitizer/prompt audit as production automatic explanation readiness.

### Recommended Commit Message

```text
Stabilize DeepSeek pro explanation benchmark
```

## LTG-08: ECharts 次日图谱成熟版

### Current Status

- ECharts initial and maturing chart contracts exist.
- Current display includes latest close, reference lines, operation zones, data credibility, and DeepSeek status.
- The cache payload now exposes `interaction_readiness_audit` and `interaction_readiness_rows` so hover/click evidence, reference-line source display, operation-zone guardrails, position-conflict visibility, DeepSeek status visibility, read-only frontend boundaries, and Streamlit parity gaps are auditable.

### Gaps

- Interaction can still be improved after the current readiness audit.
- Evidence hover/click contracts are visible, but legacy parity review remains pending.
- Operation zone details are visible through guardrail rows, but full legacy interaction comparison is incomplete.
- Position conflict visualization is present, but clarity can still be improved.
- Full parity with legacy Streamlit chart is incomplete.

### Implementation Phases

1. Finish hover/click evidence drilldown.
2. Add clearer operation zone and reference line source display.
3. Improve empty/cache-missing states.
4. Compare against legacy Streamlit visual expectations.

### Acceptance Criteria

- Missing cache state is clear.
- Available cache renders a complete chart.
- `interaction_readiness_audit` distinguishes ready contracts, blockers, and parity-pending items.
- Frontend does not compute action.
- Frontend does not mutate price, position, or `operation_zones`.
- `production_replacement_complete` remains false until legacy parity is actually complete.

### Forbidden

- Do not calculate trade action in React.
- Do not rewrite backend packet values in the chart layer.
- Do not hide freshness or credibility warnings.

### Recommended Commit Message

```text
Mature ECharts next-session operation map interactions
```

## LTG-09: Tauri Desktop Production Package

### Current Status

- Tauri preflight/dev checks exist.
- Desktop preflight now exposes `production_blocker_audit` and `production_blocker_rows`, separating dev/preflight readiness from production package readiness.
- Desktop preflight now exposes `production_runtime_contract` and `production_runtime_contract_rows`, declaring the current manual FastAPI backend startup strategy, path-only config/log policy, local API base contract, no frontend token/key exposure, no config value reads, and no log writes.
- A local `npm run tauri build` has produced a release binary on this workstation, and desktop preflight now exposes `tauri_build_artifact` so GET cache can detect `desktop/src-tauri/target/release/stock_ming_command_center` without executing build commands.
- React API client now returns a safe `backend_offline_or_unreachable` envelope when local FastAPI is unavailable, and `BackendOfflineNotice` surfaces a clear offline state with display-safe API base text, without calling providers, models, GitHub, or trades.
- Desktop preflight now exposes `backend_offline_ux_contract` and `backend_offline_ux_rows` as a static frontend source audit; packaged runtime offline UX validation remains pending.
- Desktop preflight now exposes `packaged_runtime_qa_contract` and `packaged_runtime_qa_rows`, a static package QA matrix for release artifact QA, backend startup strategy, packaged offline UX, config/log runtime paths, signing/notarization, startup external-call boundary, and secret bundle boundary.
- Production package is incomplete.

### Gaps

- Rust/Cargo production environment.
- `npm run tauri build` can produce a local release binary, but repeatable package acceptance and artifact QA are not yet complete.
- Packaged FastAPI sidecar or manual backend launch strategy validation.
- Local config path is declared as policy, but not validated in packaged runtime.
- Log path is declared as policy, but not validated in packaged runtime.
- macOS package flow.
- Friendly failure prompts exist at source-contract level; they still need packaged Tauri runtime validation.
- `packaged_runtime_qa_contract.status=packaged_runtime_qa_contract_ready_validation_pending` means the QA matrix is repeatable and visible, not that the packaged app has been opened or validated.
- `production_runtime_contract.status=runtime_contract_ready_packaged_validation_pending` means the path/startup contract is declared only; it is not packaged runtime proof.
- `tauri_build_artifact.status=artifact_detected` means a local release binary exists; it is not sidecar/offline UX/signing/notarization proof and the artifact remains ignored by git.
- `backend_offline_ux_contract.status=frontend_offline_notice_ready_packaged_runtime_validation_pending` means the React source path is ready, but the packaged app has not been opened and validated offline.
- `production_blocker_audit.status=production_package_blocked` is expected until build artifact QA, backend startup strategy, packaged offline UX, config/log runtime behavior, and macOS signing/notarization are validated.

### Implementation Phases

1. Stabilize `tauri dev` on supported local machines.
2. Define and validate FastAPI startup strategy: sidecar or explicit manual process.
3. Add production package build and artifact checks.
4. Validate config/log location behavior in packaged runtime without exposing secrets.
5. Validate packaged-runtime backend-offline UI and macOS signing/notarization flow.

### Acceptance Criteria

- `tauri dev` passes.
- `tauri build` passes.
- `tauri_build_artifact` detects the local release binary without GET cache executing `npm`, `cargo`, or Tauri.
- Backend-offline UI is friendly at React source-contract level and packaged runtime validation is separately tracked.
- Packaged runtime QA matrix is visible, keeps artifact/backend/offline/config-log/signing checks pending, and preserves startup no-external/no-trade boundaries.
- Local config and token/key are not exposed to frontend.
- `production_runtime_contract` declares config/log paths, startup strategy, and frontend secret boundary without reading config values, writing log files, starting FastAPI, or calling providers/models.
- `production_blocker_audit.package_ready=true` only after repeatable build artifact QA is verified, backend startup strategy is settled, config/log paths are validated in packaged runtime, packaged-runtime offline UX is validated, and signing/notarization is addressed.

### Forbidden

- Do not bundle secrets into frontend or app package.
- Do not claim production desktop completion from preflight only.
- Do not claim `production_runtime_contract` as packaged runtime validation; it is a path/startup policy contract.
- Do not claim a detected release binary as production package completion.
- Do not claim `backend_offline_ux_contract` as packaged runtime offline validation.
- Do not claim `packaged_runtime_qa_contract` as packaged runtime validation; it is a static QA matrix.
- Do not claim `production_blocker_audit` as production package completion while status remains `production_package_blocked`.
- Do not auto-call providers/models during app startup.

### Recommended Commit Message

```text
Package Command Center 3 Tauri desktop shell
```

## LTG-10: Streamlit 完全退出普通主流程

### Current Status

- Streamlit is marked `legacy/admin/debug`.
- Legacy cache now exposes `primary_workflow_exit_audit`, `primary_workflow_exit_rows`, and `primary_workflow_route_rows`, making the ordinary-workflow exit status visible without opening Streamlit or running legacy tools.
- Legacy cache now exposes `streamlit_fallback_dependency_contract` and `streamlit_fallback_dependency_rows`, separating Command Center 3 primary-ready routes, ordinary-flow partial fallback dependencies, and retained legacy/admin/debug dependencies. This is a local dependency contract only; it does not remove Streamlit fallback, open Streamlit, run legacy tools, create tasks, or call providers/models/GitHub.
- It has not fully exited ordinary usage paths.

### Gaps

- React/Tauri does not yet cover every ordinary operation.
- Some old tools still need Streamlit fallback.
- `primary_workflow_exit_audit.status=ordinary_workflow_exit_partial_fallback_required` is expected until all ordinary workflows are proven in Command Center 3 and fallback removal is safe.

### Implementation Phases

1. Identify ordinary user workflows still depending on Streamlit.
2. Migrate those workflows to React/Tauri + FastAPI.
3. Keep `streamlit_fallback_dependency_contract` current so every fallback dependency has a removal criterion and no feature-cut boundary.
4. Keep Streamlit for debug/admin/fallback only.
5. Preserve old-module guards.
6. Promote `primary_workflow_exit_audit` to complete only after route coverage has no fallback blockers and legacy removal is safe.

### Acceptance Criteria

- Ordinary users can use Command Center 3 desktop as the main surface.
- Streamlit does not auto-create tasks.
- Streamlit does not bypass guards.
- Legacy strong-action protection remains.
- `primary_workflow_exit_audit.ordinary_workflow_exit_complete=true` only when route coverage has no remaining Streamlit fallback dependencies and the migration checklist is clear.
- `streamlit_fallback_dependency_contract.full_streamlit_removal_ready=true` only when ordinary fallback dependencies and retained admin/debug fallback dependencies are all cleared with replacement parity proven.

### Forbidden

- Do not delete Streamlit fallback before replacement workflows are usable.
- Do not let legacy pages bypass freshness, model, or action guardrails.
- Do not present Streamlit as the primary 3.0 surface.
- Do not treat local exit audit as complete while status remains `ordinary_workflow_exit_partial_fallback_required`.

### Recommended Commit Message

```text
Retire Streamlit from primary user workflow
```

## LTG-11: 测试 / CI / Smoke / 安全扫描标准化

### Current Status

- Local test, frontend build, smoke, and diff checks are available.
- `scripts/push_gate_3_0.sh` now codifies the local push gate: Python tests, desktop build, smoke, diff check, high-risk secret scan, generated artifact scan, and final clean-worktree check.
- `scripts/push_gate_3_0.sh` can optionally write a local Markdown release-readiness report when `PUSH_GATE_REPORT_PATH` is set; report generation runs before the final clean-worktree check so unignored in-repo reports still block push.
- Secret/artifact keyword hits are separated into high-risk failures versus review output so sanitizer/test/docs mentions can be explained instead of silently ignored.
- `scripts/secret_keyword_review_contract.py` now gives the ordinary keyword scan a structured local contract: it classifies tracked keyword hits by category and top files, emits counts only, suppresses raw source lines, and fails if high-risk tracked secret-looking values appear outside tests/docs. It does not call external services or prove periodic human allowlist review is complete.
- `GET /api/audit/cache` now exposes `release_gate_readiness_audit`, `release_gate_readiness_rows`, and local workflow inventory. This is a static local contract check for `scripts/push_gate_3_0.sh`, not a CI status check and not production completion proof.
- `.github/workflows/command-center-3-push-gate.yml` now mirrors the local push gate by creating `.venv`, installing desktop dependencies, and running `scripts/push_gate_3_0.sh` with `PYTHON_BIN=.venv/bin/python`.

### Gaps

- CI mirror workflow exists, but remote CI status is still not local proof until a pushed run is inspected; current audit only proves static workflow presence.
- Push gate still needs periodic review of false-positive allowlists; current audit keeps `false_positive_allowlist_review_pending` visible.
- Structured keyword review is present, but it is still a local classification contract; periodic human allowlist review and remote CI evidence remain separate.
- Optional local reports are evidence for one gate run, not durable CI status and not production completion proof.

### Implementation Phases

1. Document the release gate in one place.
2. Keep `unittest`, frontend build, smoke, and `git diff --check` mandatory.
3. Add repeatable secret and generated-artifact scan commands.
4. Keep ordinary keyword review structured and count-only so logs do not expose raw matched source lines.
5. Keep optional local release-readiness reports explicit and outside tracked artifacts unless intentionally reviewed.
6. Add CI coverage where safe and affordable.

### Acceptance Criteria

- Python tests pass.
- Frontend build passes.
- `scripts/smoke_3_0.sh` passes.
- `git diff --check` passes.
- Secret scan and generated artifact scan are clean or explained.
- Ordinary keyword review contract runs after high-risk scan, emits no raw matched source lines, and keeps periodic allowlist review visible as pending.
- Worktree is clean before push.
- Optional local release report records passed checks, branch/head, ahead count, and safety boundaries without pushing or calling providers.
- `release_gate_readiness_audit.local_gate_ready=true` and `ci_mirror_ready=true` are visible in the audit cache, while `release_gate_complete` remains false until allowlist review and actual remote check evidence are proven.

### Forbidden

- Do not bypass failing tests.
- Do not use `git add .`.
- Do not push without user confirmation.

### Recommended Commit Message

```text
Add release gate readiness audit
```

## LTG-12: 真实交易链路继续保持隔离

### Current Status

- Automatic real trading is not connected.
- Multiple packets and APIs declare `does_not_execute_trades` and `does_not_modify_strategy_action`.
- `GET /api/risk/cache` now exposes `trade_isolation_audit`, `trade_isolation_rows`, and `trade_isolation_boundary_rows`: a cache-only audit of risk policy, task catalog POST route boundaries, and frontend no-trade/no-action visibility.

### Gaps

- Future productionization could accidentally blur research and execution boundaries.
- Any eventual trading integration would need a separate project, separate approvals, and separate safety design.
- The audit proves current Command Center 3 cache/task/frontend contracts, not a future broker/order integration design.

### Implementation Phases

1. Keep all current 3.0 migration work research/client-side only.
2. Preserve action mutation guards in cache, task, frontend, model, factor, storage, and worker paths.
3. Add tests whenever a new route or task can affect decision-adjacent data.

### Acceptance Criteria

- No automatic order path exists.
- Research/factor/model/cache/frontend paths cannot mutate `strategy action`.
- Any future trade integration is explicitly out of this roadmap unless a separate approved design exists.
- `trade_isolation_audit.status=trade_isolation_ready`, with zero blockers and all known POST routes covered by the task catalog.

### Forbidden

- Do not connect broker/order APIs in ordinary migration work.
- Do not execute real trades.
- Do not let model or factor output become orders.

### Recommended Commit Message

```text
Keep real trading isolated from Command Center 3 automation
```

## LTG-13: 下一票雷达快扫生产化

### Current Status

- Legacy module already has a next-ticket radar concept.
- Command Center 3 has a React cache page and candidate-radar cache surface.
- The migration has reduced UI stall risk by separating page render, cache reads, and task execution.
- Local `quick_cache_scan`, `watchlist_scan`, and `custom_pool_scan` task modes exist: they read local snapshot/payload, write a SQLite candidate-radar packet, and show coverage/freshness/local-pool gaps without external calls.
- The 3.0 page now exposes legacy signal-group coverage, parity inventory, output contract rows, local candidate-pool audit, skipped reasons, scan mode status, freshness state, provider coverage rows, degraded mode rows, and universe-size coverage detail.
- Candidate radar packets now include `scan_execution_summary` and `scan_acceptance_rows` so cache view, local scan, local pool scan, and full-pool plan-only outputs can be audited without treating them as production full-pool completion.
- A button-gated local `run_candidate_radar_full_pool_plan` task now writes `full_pool_scan_plan`, stage rows, filter rows, required signal rows, and blocker rows; it is a plan-only readiness packet, not a full-pool scan.
- A button-gated local `run_candidate_radar_deep_scan_plan` task now writes `deep_scan_plan`, stage rows, parity rows, required signal rows, and blocker rows so fast-scan migration can audit no-feature-loss readiness without executing deep scan, refreshing providers, or calling DeepSeek.
- Candidate radar packets now expose `fast_scan_readiness_audit` and `fast_scan_readiness_rows`, proving the local quick/watchlist/custom scan contract is cache/task based, page render does not scan, legacy/provider/freshness gaps are visible, and full-pool/deep-scan remain pending rather than silently downgraded.
- Candidate radar packets now expose `fast_scan_runtime_budget_contract` and `fast_scan_runtime_budget_rows`: local sync display is capped, local pool input normalization has a fixed budget, large universes must move to worker execution, and truncation is reported as a visible gap instead of being hidden.
- Candidate radar packets now expose `no_feature_loss_acceptance_contract` and `no_feature_loss_acceptance_rows`: this aggregates page-render/cache boundaries, local scan modes, legacy signal groups, legacy output fields, provider/freshness gaps, runtime budget, browser performance trace status, full-pool/deep-scan execution status, provider-backed acceptance, and trade/action isolation. It makes the local no-feature-loss QA surface visible but keeps `production_radar_replacement_complete=false`.
- Current 3.0 radar path is still not a full replacement for the legacy radar workflow.

### Gaps

- Need actual full-pool scan execution beyond the current local quick/watchlist/custom scans and full-pool readiness plan.
- Need worker-backed async execution for slower scans beyond the local fallback path.
- Deeper local scan coverage accounting and scan acceptance rows now exist for universe size, provider-blocked groups, stale inputs, missing provider data, degraded modes, freshness, local pool, full-pool boundary, and trade isolation; they are still cache/local-only and do not prove full-pool or provider-backed scan acceptance.
- Need clear distinction between quick scan, deep-scan readiness plan, real deep scan, and research-only candidates.
- The deep-scan readiness plan is not deep scan execution and does not prove legacy radar replacement.
- Browser performance trace and packaged runtime UI responsiveness validation are still pending; the current runtime budget is a static/local contract.
- The no-feature-loss acceptance contract is local QA; it does not prove browser performance, real full-pool/deep-scan execution, or provider-backed parity acceptance.
- `fast_scan_local_ready_full_pool_pending` is not production replacement; it only proves local readiness and visible gaps.
- Need parity acceptance before removing any Streamlit fallback.

### Implementation Phases

1. Inventory legacy radar inputs, scoring fields, filters, exclusions, and output packet shape.
2. Build a fast local scan task that reads existing cache/storage first and returns a task receipt immediately.
3. Add progressive scan modes: `quick_cache_scan`, `watchlist_scan`, `custom_pool_scan`, `full_pool_plan`, `deep_scan_plan`, and later real `full_pool_scan` / `deep_scan`.
4. Add coverage metrics so the UI shows what was scanned, skipped, stale, or blocked.
5. Preserve signal parity before removing any legacy fallback.
6. Move slow provider refreshes behind explicit POST tasks instead of radar page render.

### Acceptance Criteria

- Page render does not start full-market scanning.
- POST scan returns `task_id` quickly and writes a candidate radar packet when done.
- React shows progress, last successful packet, coverage, skipped reasons, and freshness state.
- Existing legacy radar signal groups are mapped or explicitly marked as not yet migrated.
- Missing provider data, provider-blocked groups, stale inputs, and degraded modes are reported as coverage gaps, not silently dropped.
- Local quick scan enforces and displays sync runtime budgets, including candidate display caps and local pool input caps.
- Full-pool plan lists worker requirements, filters, required signal groups, and blockers without scanning or refreshing providers.
- Deep-scan plan lists no-feature-loss parity rows, required signal rows, freshness, worker blockers, and trade/model boundaries without executing deep scan or calling DeepSeek.
- `fast_scan_readiness_audit.local_fast_scan_ready=true` only when page-render, local task, legacy gap, provider gap, freshness, last-cache, full-pool, deep-scan and trade boundaries are all visible.
- `no_feature_loss_acceptance_contract.local_no_feature_loss_contract_ready=true` only means the local QA surface is visible; `production_radar_replacement_complete` remains false until browser performance, real full-pool/deep-scan execution, and provider-backed parity acceptance are complete.
- `production_radar_replacement_complete` remains false until real full-pool/deep-scan execution and provider-backed parity acceptance are complete.
- Radar output does not become a buy instruction and does not modify `strategy action`.

### Forbidden

- Do not scan the full market on page load.
- Do not treat `full_pool_scan_plan` as full-pool scan completion.
- Do not treat `deep_scan_plan` as deep scan completion or legacy radar replacement.
- Do not reduce legacy radar signal coverage without marking the gap.
- Do not hide candidate display truncation or local pool input truncation.
- Do not treat `no_feature_loss_acceptance_contract` as proof of production radar replacement.
- Do not call Tushare/DeepSeek/GitHub from GET cache or render.
- Do not treat candidates as trade instructions.

### Recommended Commit Message

```text
Productionize non-blocking next-ticket radar scans
```

## LTG-14: Command Center 3 动效与可视化清晰度优化

### Current Status

- Current React UI is functional and audit-oriented.
- A first motion clarity layer exists for route staging, cards, metric tiles, task panels, progress state, focus rings, and reduced-motion fallback.
- Navigation now exposes `aria-current` / `data-route-active` plus a finite active-route context sweep, and status badges expose `data-status-tone` plus a small visual tone dot so users can see current context and state without reading every label.
- Cache/page state, task receipts, task status panels, and candidate-radar state now share a CSS-only `StateClarityRail` that makes accepted/running/blocked/done boundaries visible without timers, requestAnimationFrame, recomputation, or external calls.
- Cache loading/error/empty states, task phase panels, and task creation receipts now expose a shared `state_change_confirmation` motion scope with finite `cc-phase-confirm` cues, so refresh and task transitions are visible without adding timers, provider calls, or recomputation.
- `scripts/motion_viewport_qa_contract.py` now pins the LTG-14 browser QA route/viewport matrix and is run by `scripts/push_gate_3_0.sh`; it is a local static contract and still reports `visual_qa_complete=false`.
- Next-session ECharts now has a short update clarity layer and respects reduced-motion preferences by disabling chart update animation.
- Candidate radar now tags its primary result cluster with cache/coverage/blocker/degraded state so result transitions are visually easier to follow without recomputing candidates.
- Current motion is CSS-only, finite-duration, and visual-only; it does not change packet values, task behavior, strategy action, or external-call boundaries.
- Call Ledger Audit now exposes `motion_clarity_audit` and `motion_clarity_rows`, a local static source audit for motion tokens, finite keyframes, navigation/status context cues, reduced-motion CSS/runtime behavior, StateClarityRail usage, chart/radar clarity scopes, layout containment, no timer/RAF motion loops, and no provider invocation markers.
- Call Ledger Audit now exposes `motion_production_qa_contract` and `motion_production_qa_rows`, a local production acceptance checklist for purposeful motion tokens, state-change clarity, chart/radar scopes, reduced-motion accessibility, layout readability, no timer/RAF loops, browser visual QA, performance trace, and provider/trade isolation. It keeps `production_motion_complete=false` until browser visual and performance checks are run.
- Further polish should improve clarity without distracting from risk, freshness, and decision boundaries.

### Gaps

- Need deeper transitions for panel expansion and later candidate-radar result deltas beyond the primary cluster, clarity rail, and static phase-confirm cue.
- Need broader chart motion verification so updates help users understand state changes instead of adding decoration.
- Need browser viewport execution against the pinned route/viewport matrix so animation never overlaps, occludes, or resizes critical text.
- Need runtime performance traces so later animation never reintroduces UI stalls.
- Need visual hierarchy that makes status, freshness, blockers, and candidate changes obvious.
- Current navigation/status cue layer improves static context visibility but still needs browser viewport review for dense pages and mobile widths.
- `motion_clarity_static_ready_visual_qa_pending` is not production motion completion; it only proves static source guardrails.
- `motion_production_qa_local_ready_visual_perf_pending` is also local QA only; it does not prove browser visual quality or runtime performance.

### Implementation Phases

1. Define a restrained motion system inspired by high-end product keynotes: clear staging, smooth state changes, and low visual noise.
2. Add motion tokens for duration, easing, delay, opacity, transform, and chart update transitions.
3. Apply motion first to task progress, cache refresh, page transitions, ECharts updates, and candidate-radar scan results.
4. Add reduced-motion fallbacks and performance checks.
5. Verify desktop and mobile viewports so animation does not overlap, occlude, or resize critical text.

### Acceptance Criteria

- Animation clarifies state transitions and does not hide data.
- `prefers-reduced-motion` is respected.
- Main pages remain responsive during chart and task updates.
- Motion does not trigger external calls or recomputation.
- No animation changes `strategy action`, price, position, or packet values.
- Cache/task/radar clarity states are visible without using timers, requestAnimationFrame, provider refreshes, or frontend scoring.
- Cache/task phase confirmation cues are visible and audited as visual-only state changes.
- The motion viewport QA contract is repeatable in the push gate, while browser execution remains explicit and pending.
- Visual polish is additive and does not replace audit labels, warnings, or freshness state.
- `motion_production_qa_contract.local_motion_qa_ready=true` only means the local production checklist is visible and source guardrails pass; visual QA and performance trace must remain pending until explicitly executed.
- `motion_clarity_audit.static_ready=true` is allowed only when static source checks pass.
- `production_motion_complete` remains false until browser viewport and performance QA are complete.

### Forbidden

- Do not add decorative motion that obscures evidence, warnings, or risk state.
- Do not animate by recomputing backend data.
- Do not use motion to imply certainty, urgency, or trade recommendations.
- Do not regress text readability or viewport layout.

### Recommended Commit Message

```text
Add Command Center 3 motion clarity system
```

## Priority Route

| priority | focus | note |
|---|---|---|
| P0 | Current unpushed commit push gate | Use `git log origin/main..HEAD` as the authoritative unpushed list; run `scripts/push_gate_3_0.sh`, review results, wait for user confirmation, then push. |
| P1 | A 股交易日历 freshness 生产验收 | This blocks trustworthy current evidence. |
| P2 | Tushare 全接口真实流水线 | Validate provider data groups one by one through button-gated tasks. |
| P3 | Factor Test Lab 真实小股票池研究 | Promote from light research metrics to research-grade validation. |
| P3a | 下一票雷达快扫生产化 | Restore radar scan capability in 3.0 without UI stalls or signal loss. |
| P4 | Storage / Worker 生产化 | Make heavy work reliable and auditable. |
| P5 | DeepSeek pro 稳定性提升 | Improve JSON stability while keeping manual/default-off governance. |
| P6 | Tauri production package | Turn dev/preflight shell into user-openable desktop package. |
| P7 | Streamlit 完全退场 | Move ordinary workflows to Command Center 3 after replacement is ready. |
| P8 | 动效与可视化清晰度优化 | Add polished motion after core data, worker, and desktop paths are stable. |

## Risk Boundaries

- cache API 不自动外联。
- POST task 才可能外部调用。
- Tushare 不在页面启动时自动调用。
- DeepSeek 不在页面启动时自动调用。
- GitHub probe 不在页面启动时自动调用。
- DeepSeek 不作为数据源。
- Factor 分数不直接改 `strategy action`。
- 下一票雷达不在页面启动时做全市场扫描。
- 雷达候选不作为买入指令。
- 动效只增强可读性，不暗示交易确定性或紧迫性。
- stale / expired / historical 数据不进当前 evidence。
- 真实交易未接入自动链路。
- token/key 不进前端、不进日志、不进 packet、不进 cache。
- `node_modules` / `dist` / `target` / Parquet / DB / cache 不进 git。

## Documentation Maintenance Rules

- Update this document when a long-term goal changes status.
- If a goal becomes production-ready, add the acceptance evidence and link to tests or smoke output.
- Distinguish `done_real`, `scaffold`, `preflight`, `mock`, `matrix`, and `sanitizer`.
- Do not call scaffold or preflight work production complete.
- Do not treat mock, matrix, or sanitizer as external acceptance.
- Keep commit messages narrow and tied to one goal whenever possible.
