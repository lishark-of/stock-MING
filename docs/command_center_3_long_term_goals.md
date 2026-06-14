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

## Runtime Mode Layering Baseline

The long-term boundary is not a permanent ban on all startup-side automation. It is a default-deny, mode-based runtime model. `cache_only` remains the safe default for smoke, CI, quick reads, and disconnected review. Future local-investment-client workflows may opt into `live_light`, but only through auditable FastAPI `POST` tasks, never direct React provider calls or cache GET side effects.

| mode | behavior | external_calls | use_case | default |
|---|---|---|---|---|
| `cache_only` | Read existing cache only. GET cache and React render never call providers or models. | none | smoke / CI / quick view / offline review | yes |
| `manual` | User clicks an explicit button or submits an explicit task. | only the selected task may call Tushare, DeepSeek, or GitHub probe |稳健投研与验收 | no |
| `live_light` | After initial cache render, React may create one rate-limited background bootstrap task. | light Tushare refresh and optional DeepSeek pro explanation through POST task / worker / local fallback | 本地日常投研客户端 | no |
| `live_full` | Reserved for full-pool or deep-scan production work. | future explicit worker mode only | 全池/深扫，不默认启用 | no |

Recommended future configuration keys:

```text
COMMAND_CENTER_BOOTSTRAP_MODE=cache_only | manual | live_light | live_full
COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN=false
COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN=false
COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT=20
COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS=600
COMMAND_CENTER_LIVE_DEEPSEEK_MODEL=deepseek-v4-pro
COMMAND_CENTER_LIVE_ALLOW_FULL_POOL=false
```

`live_light` target behavior is intentionally narrow: the page must render from cache first, create at most one background bootstrap task inside the rate limit, show the current mode and task status, and degrade safely when the task fails. The task may refresh current target / holdings / watchlist light data, refresh factor and next-session caches, and optionally enqueue a governed DeepSeek pro explanation after data is ready. It must not block UI, mutate `strategy action`, change prices or holdings, write `operation_zones`, execute trades, or expose token/key material.

This mode layering also applies to search-driven research. A future stock search or "生成 3.0 量化推演" action should create a POST task that validates the symbol, refreshes allowed light data, writes call ledger/model ledger, updates Factor Quant Hub and Next Session cache, and displays provenance, freshness, DeepSeek status, and chart results. It remains research-only and cannot turn DeepSeek text, factor scores, or radar candidates into buy/sell instructions.

## Remaining Goals Snapshot

Current snapshot date: 2026-06-14.

Strict completion status: none of the 14 long-term goals should be closed as fully complete yet. LTG-11 and LTG-12 are the closest to stable operating policy, but they still remain ongoing release boundaries rather than one-time completed features.

Progress summary as of 2026-06-14: the Command Center 3.0 migration foundation is roughly 70% established, while production acceptance across the 14 LTGs is roughly 25-35% complete. The strict closeout count remains `0 / 14` because every LTG still has at least one provider-backed, packaged-runtime, browser-performance, worker/storage, or retirement acceptance item pending.

| bucket | count | goals | current meaning |
|---|---:|---|---|
| Mostly stable guardrails | 2 | LTG-11, LTG-12 | Local gate and real-trading isolation are working release boundaries, but must keep running on every push candidate. |
| Real validation still required | 5 | LTG-01, LTG-02, LTG-03, LTG-04, LTG-13 | The codebase has local contracts, scaffolds, or light paths, but production acceptance still needs real provider data, real pools, or browser/performance proof. |
| Productionization still required | 5 | LTG-05, LTG-06, LTG-07, LTG-08, LTG-09 | Storage, worker, model explanation, chart parity, and desktop package have useful preflight/contracts, but are not production complete. |
| Dependent retirement goal | 1 | LTG-10 | Streamlit can only exit ordinary workflow after React/Tauri parity and fallback safety are proven. |
| Later polish goal | 1 | LTG-14 | Motion clarity should continue after core data, worker, desktop, and radar validation are stable. |

Quota guidance while weekly budget is low: do not start broad new development when the remaining weekly quota is around 20%. Prefer final push-gate review, user-confirmed push, and short documentation handoff. Resume P1/P2/P3 validation work after quota resets or when a narrow acceptance run is explicitly requested.

## Long-Term Goals Table

| id | long_term_goal | current_status | target_state | priority | success_criteria |
|---|---|---|---|---|---|
| LTG-01 | A 股交易日历级 freshness 生产化 | `done_real` MVP, still needs production validation | All current evidence is gated by expected trade date | P1 | stale / expired / historical / unknown data cannot enter score, support, evidence preview, or action. |
| LTG-02 | Tushare 全接口生产流水线 | core light path `done_real`; extended APIs `matrix` / `mock`; `live_light` bootstrap remains future work | All selected interfaces run through task pipeline with call ledger and mode-gated refresh rules | P2 | Each interface has real target samples, safe failure states, no false verified claims, and no cache/render direct provider calls. |
| LTG-03 | Factor Test Lab 完整生产化 | light research metrics `done_real`; production QA contract visible; production research incomplete | Research-grade factor validation for single factors | P3 | IC, Rank IC, ICIR, groups, cost, drawdown, sample split, decay, and neutral IC are auditable and research-only. |
| LTG-04 | Factor 全市场 / 股票池研究 | light mode plus local read-plan and execution readiness audit; batch execution pending | watchlist / custom pool / full pool research pipeline | P3 | Large universe runs in task pipeline without blocking UI or entering strategy action. |
| LTG-05 | Storage / DuckDB / Parquet 生产化 | dataset scaffold, dry-runs, query policy, and push-gate contract exist | Versioned, queryable local data layer | P4 | schema/version/TTL/compaction/query services are auditable; data artifacts stay out of git. |
| LTG-06 | Worker / Celery / Redis 生产化 | local task fallback, preflight, blocker audit, healthcheck QA contract, readiness/activation receipts, and push-gate contract exist | Production-capable worker orchestration with local fallback | P4 | POST returns task_id, worker runs heavy jobs, Redis absence falls back gracefully, scheduler stays off by default. |
| LTG-07 | DeepSeek pro 稳定解释生产化 | manual governance, sanitizer, local JSON stability audit, response-format review, activation receipt, and push-gate contract exist; mini-benchmark below production target; `live_light` auto explanation remains future work | Stable manual explanation, optional mode-gated background explanation after data tasks | P5 | JSON success rate > 90%, no action leakage, no numeric overwrite, cost predictable, and failed parse never contaminates packets. |
| LTG-08 | ECharts 次日操作图谱成熟版 | maturing chart contract with interaction readiness audit; legacy parity pending | React/ECharts replaces Streamlit main next-session visual | P5 | Complete cache display, evidence interactions, no frontend action/price/position mutation. |
| LTG-09 | Tauri desktop production package | dev/preflight with runtime contract and local executable release binary QA; `.app`/DMG packaged runtime QA pending | Production desktop shell for ordinary users | P6 | tauri dev/build pass; backend-offline state is friendly; config/log policy is validated; token/key never enters frontend. |
| LTG-10 | Streamlit 完全退出普通主流程 | `legacy/admin/debug` marked, fallback dependency contract visible, still used for fallback | Streamlit only for debug/admin/fallback | P7 | Ordinary research workflow runs through Command Center 3 desktop. |
| LTG-11 | 测试 / CI / smoke / 安全扫描标准化 | local tests, smoke, and local contract guards exist | Repeatable gate for every release candidate | P0/P4 | unittest, frontend build, smoke, diff check, secret scan, artifact scan, and local LTG contracts are documented and enforced. |
| LTG-12 | 真实交易链路继续保持隔离 | auto trading not connected | Trading remains explicitly out of automatic chains | Always | No automatic order path; strategy action cannot be mutated by research/cache/model/frontend paths. |
| LTG-13 | 下一票雷达快扫生产化 | local fast-scan readiness, no-feature-loss QA, legacy parity acceptance receipt, local full-pool execution receipt, local deep-scan review receipt, and push-gate contract exist; provider-backed full-pool/deep-scan acceptance pending; search-to-quant projection remains future mode-gated work | Fast radar scan and search-driven quant projection in Command Center 3 without feature loss or degraded signal coverage | P3 | Radar and search tasks run through task pipeline, preserve legacy signal groups, avoid UI stalls, and report coverage gaps instead of hiding them. |
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
- Data Health now exposes `current_evidence_decision_surface_audit`, a local snapshot-only audit of visible `composite_score`, `support_factors`, `evidence_preview`, `next_session_bridge.preview`, and `strategy_action` fields. It shows blockers when research-only current evidence still has visible score/support/preview values, but it does not rescore, filter packets, mutate action, or prove provider-backed acceptance.
- Data Health now exposes `current_evidence_producer_coverage_audit`, a local snapshot-only audit that checks visible current-evidence producers for `expected_trade_date`, `data_date`, and `freshness_state` coverage. Missing producers remain `not_observed`, not production proof.
- `scripts/data_health_freshness_contract.py` now runs in `scripts/push_gate_3_0.sh` to guard LTG-01 contracts against unsafe regressions: local-only boundaries must remain visible, provider-backed acceptance must remain pending until explicit provider validation, and no Data Health contract may imply external calls, real trades, or strategy action mutation.
- Data Health now exposes `trade_cal_provider_acceptance_runbook`, a local execution checklist for future provider-backed `trade_cal` long-window acceptance. It fixes the explicit POST task route, safe payload, call-ledger evidence, schema/window/holiday coverage, failure modes, artifact promotion boundary, and current-evidence isolation, while keeping `provider_backed_long_window_acceptance_done=false`.
- Data Health now exposes `trade_cal_provider_acceptance_promotion_audit`, a local snapshot-only evidence promotion audit. It requires prior provider call ledger evidence, safe ledger fields, a 730-day window, schema/local artifact cross-check, open/closed/current coverage, freshness replay, failure-mode evidence, current-evidence boundary recheck, and an explicit promotion marker before `trade_cal` acceptance can move out of pending; the audit itself never calls Tushare.
- Data Health now exposes `freshness_production_blocker_audit`: a local read-only blocker summary across the freshness matrix, long-window replay fixture, local `trade_cal` artifact validation, provider-backed promotion evidence, current-evidence boundary, decision-surface isolation, and producer expected-date coverage.
- Data Health now exposes `freshness_provider_acceptance_readiness_receipt`: a local read-only receipt that tells whether LTG-01 is ready for an explicit POST `trade_cal` provider acceptance task, what evidence is still missing before promotion, and which shortcuts remain forbidden. It keeps `production_freshness_gate_complete=false`.
- Data Health now exposes `freshness_provider_acceptance_activation_receipt`: a local activation checklist for the future explicit `trade_cal` provider acceptance task. It keeps provider task execution, provider call ledger evidence, explicit promotion marker, and production completion pending while confirming GET cache and React render do not call Tushare/DeepSeek/GitHub or mutate action.
- Tushare refresh task call-ledger rows can now record explicit `acceptance_mode=provider_backed_trade_cal_long_window` evidence for future provider-backed `trade_cal` acceptance: 730-day window, `cal_date/is_open` schema, open/closed row counts, latest completed trading day, freshness replay evidence, failure-mode evidence, and no-trade/no-action boundaries. This is still button-gated POST evidence, not GET cache execution.
- Data Health can now read the persisted local `command_center_tushare_refresh_packet` from SQLite as prior `trade_cal` acceptance evidence. The lookup is cache-only/read-only, does not create tasks, does not call Tushare, and still requires the promotion audit plus local artifact/current-evidence checks before readiness can clear.

### Gaps

- Full A-share trading-calendar production acceptance is not complete.
- Needs provider-backed long-window `trade_cal` acceptance evidence beyond the local artifact check.
- Needs holiday, weekend, post-close data availability, and most recent completed trading day acceptance.
- Needs provider-backed acceptance that proves the local artifact was produced and refreshed through the explicit task/storage pipeline, not merely present on disk.
- The acceptance matrix is a contract, the synthetic sample is a fixture, the local Parquet validation is a physical artifact check, the current-evidence QA contract is a boundary contract, and the decision-surface / producer-coverage audits are snapshot-only visibility checks; none of them call Tushare on page render.
- The provider acceptance runbook is not provider execution; it only makes the real Tushare `trade_cal` acceptance pass reproducible and keeps local artifact validation separate from provider-backed evidence.
- The provider acceptance promotion audit is not provider execution; it only decides whether prior local evidence is strong enough to promote acceptance, and defaults to pending when evidence is missing or incomplete.
- The freshness production blocker audit is not production completion; it only makes LTG-01 blockers visible and keeps `production_freshness_gate_complete=false`.
- The provider acceptance readiness receipt is not provider execution; it only clarifies the next allowed step and missing evidence. It cannot promote synthetic fixtures, local Parquet checks, runbooks, or page renders to provider-backed acceptance.
- The provider acceptance activation receipt is not provider execution; it is the final local checklist before a future explicit POST task. It cannot call Tushare, create tasks, promote fixtures/artifacts/runbooks, mutate strategy action, or mark production freshness complete.
- A `trade_cal` call-ledger row with `acceptance_mode=provider_backed_trade_cal_long_window` is not enough by itself. It only becomes provider-backed long-window evidence when the explicit task also records successful provider rows, 730-day schema/window checks, freshness replay evidence, and failure-mode evidence.
- Reading the persisted Tushare refresh packet in Data Health is not provider execution. It only lets the cache audit discover prior POST task evidence from SQLite; stale, partial, matrix-only, or non-`trade_cal` rows cannot be promoted by the lookup alone.

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
- Data Health shows `current_evidence_decision_surface_audit` and rows: visible score/support/preview surfaces are marked `not_observed`, `passed_read_only_audit`, or blocker states; missing visible fields are not treated as production proof.
- Data Health shows `current_evidence_producer_coverage_audit` and rows: visible producers must carry expected trade date, data date, and freshness state; absent producers are `not_observed` and cannot be used as proof that every producer is production-ready.
- Push gate runs `scripts/data_health_freshness_contract.py` and fails if Data Health contracts lose local-only/no-provider/no-trade/no-action boundaries or falsely claim provider-backed freshness completion.
- Data Health shows `trade_cal_provider_acceptance_runbook` and rows: explicit POST task requirement, safe payload, call ledger, long-window sample, schema, local artifact cross-check, freshness replay, failure modes, artifact promotion, current-evidence boundary, and secret/trade boundary.
- Data Health shows `trade_cal_provider_acceptance_promotion_audit` and rows: explicit prior provider call ledger, safe call-ledger fields, minimum long-window evidence, schema/local artifact cross-check, open/closed/current coverage, freshness replay evidence, failure-mode evidence, current-evidence boundary recheck, explicit promotion marker, and read-only no-provider-call boundary.
- Data Health shows `local_tushare_refresh_packet_summary` when a local Tushare refresh packet exists: source cache, selected APIs, call-ledger counts, `trade_cal` evidence row count, no-provider lookup flags, and non-completion flags.
- Data Health shows `freshness_production_blocker_audit` and rows: every production phase is marked passed, pending, or blocked, with provider-backed `trade_cal`, local artifact, current-evidence, decision-surface, and producer expected-date blockers visible.
- Data Health shows `freshness_provider_acceptance_readiness_receipt` and rows: explicit POST route readiness, cache/render no-provider boundary, current-evidence boundary, decision-surface isolation, producer expected-date coverage, provider evidence ticket, and production-completion boundary.
- Data Health shows `freshness_provider_acceptance_activation_receipt` and rows: readiness receipt visibility, explicit POST task requirement, provider execution evidence required, promotion review required, current-evidence boundary, decision-surface isolation, producer expected-date coverage, fixture/artifact not acceptance, cache/render no-provider boundary, production-completion boundary, and no-trade/no-action boundary.
- Local `trade_cal` Parquet validation can pass without setting provider-backed acceptance to done.

### Forbidden

- Do not silently treat unknown freshness as current evidence.
- Do not let stale / expired / historical rows modify `strategy action`.
- Do not hide fallback calendar state.
- Do not treat synthetic samples, local matrix rows, or local artifact checks as provider-backed production acceptance.
- Do not treat `trade_cal_provider_acceptance_runbook.local_runbook_ready=true` as evidence that Tushare was called or provider-backed acceptance passed.
- Do not treat `trade_cal_provider_acceptance_promotion_audit.promotion_ready=false` as a failure of the cache API; it means prior provider-backed evidence is still missing or incomplete.
- Do not treat `freshness_production_blocker_audit.production_ready=true` as final production completion; it only means local blocker rows are clear enough for promotion review, while release completion still needs explicit acceptance and gate evidence.
- Do not treat `freshness_provider_acceptance_readiness_receipt.ready_for_explicit_provider_task=true` as provider-backed acceptance; it only means the next safe step is a user-triggered POST task.
- Do not treat `freshness_provider_acceptance_activation_receipt.local_activation_receipt_ready=true` as provider-backed acceptance, provider task execution, or production freshness completion.
- Do not treat `current_evidence_decision_surface_audit` as runtime rescore, packet filtering, or provider-backed freshness proof.
- Do not treat `current_evidence_producer_coverage_audit` as building missing packets, refreshing providers, or proving full producer coverage when rows are `not_observed`.
- Do not treat `scripts/data_health_freshness_contract.py` passing as real `trade_cal` provider acceptance; it only blocks local contract regressions.

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
- Tushare refresh packets now expose `request_parameter_qa_contract`: a local per-interface parameter contract for safe request params, `ts_code` preflight blocking, date context visibility, alias handling, and matrix-only boundaries.
- Tushare refresh packets now expose `provider_target_sample_plan_contract`: a local target-domain sample plan for `trade_cal`, margin, dragon-tiger, limit/emotion, chip, financial disclosure, and hard-risk interfaces. It declares required APIs, sample windows, request context, success evidence, and failure evidence for future provider-backed acceptance.
- Tushare refresh packets now expose `provider_acceptance_promotion_audit`: a local call-ledger promotion audit that requires all declared APIs selected, all non-empty successful samples, all target groups validated, safe semantic audit, no pending target sample groups, explicit provider-backed acceptance marker, and failure-mode evidence before acceptance can be promoted.
- Tushare refresh packets now expose `provider_evidence_gap_audit`: a local target-domain evidence gap ledger that reads existing call-ledger rows, target validation rows, sample-plan rows, target-sample acceptance rows, and promotion audit state, then lists missing provider evidence per target domain without calling Tushare or promoting acceptance.
- Tushare refresh packets now expose `provider_sample_readiness_receipt`: a local receipt that says whether the next safe step is an explicit POST target-sample acceptance task, promotion evidence review, or completing target sample payload/selection. It now also reports target-sample acceptance review-ready evidence, while keeping matrix, local QA, fake/local adapter, and gap-ledger evidence out of provider-backed acceptance promotion.
- Tushare refresh packets now expose `provider_sample_activation_receipt`: a local activation checklist for future explicit target-sample provider acceptance. It keeps provider task execution, safe provider call ledger rows for every target domain, explicit full-interface acceptance marker, and production completion pending while confirming GET cache and React render do not call Tushare/DeepSeek/GitHub or mutate action.
- Tushare refresh packets now expose `provider_target_sample_acceptance_contract`: an explicit `provider_target_sample_acceptance` payload review layer that can mark one or more target domains as review-ready from button-task call ledger evidence, while keeping full-interface acceptance, production completion, GET/render provider calls, and strategy action mutation false.
- The local LTG-02 contract and service tests now cover multi-target review-ready evidence for dragon-tiger, limit/emotion, chip distribution, financial disclosure, and hard-risk domains in one explicit target-sample acceptance pass. This is still local/fake evidence plumbing only: it does not call real Tushare, does not promote provider-backed acceptance, and does not complete the production Tushare pipeline.
- Tushare refresh packets now expose `provider_target_sample_runbook_contract`: a local provider-sample review checklist that pins the explicit POST route, required `provider_target_sample_acceptance` mode, required APIs, payload context fields, call-ledger evidence checklist, gap-ledger blockers, and promotion-review boundary for every requested target domain. It does not call Tushare, create tasks, promote local/fake samples, or complete production acceptance.
- `scripts/tushare_acceptance_contract.py` is now part of the local push gate. It exercises only local matrix/readiness contract helpers and prevents matrix-only rows, failure-mode QA, request-parameter QA, target-sample plans, or provider-readiness audits from being mistaken for provider-backed production acceptance.
- `POST /api/tasks/refresh-tushare-facts` now exposes an explicit `provider_backed_trade_cal_long_window` call-ledger evidence mode for future `trade_cal` provider acceptance. It does not run by default, does not make `trade_cal` full-interface acceptance, and still requires replay/failure-mode evidence before provider-backed long-window acceptance can be marked on the ledger row.

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
- `request_parameter_qa_contract.status=request_parameter_qa_ready_provider_acceptance_pending` proves local parameter contracts are visible and secret-safe; it does not prove that each interface has correct real provider windows.
- `provider_target_sample_plan_contract.status=local_plan_ready_provider_execution_pending` proves the target sample acceptance plan is explicit; it does not execute Tushare or prove provider-backed samples.
- `provider_acceptance_promotion_audit.status=provider_acceptance_promotion_pending` is expected until prior full-interface provider evidence is explicit; fake adapter, matrix-only rows, local QA, target sample plans, and readiness audits cannot promote acceptance by themselves.
- `provider_evidence_gap_audit.status=provider_evidence_gaps_pending` is expected while any target domain lacks required selection, call-ledger evidence, non-empty samples, failure-mode evidence, sample-plan readiness, target-sample acceptance review evidence, or explicit promotion readiness.
- `provider_sample_readiness_receipt.status=provider_sample_receipt_ready_execution_pending` only means a user-triggered POST provider-sample task is the next safe step for ready targets; it is not provider-backed acceptance or production completion.
- `provider_sample_activation_receipt.status=provider_sample_activation_ready_execution_pending` or `provider_sample_activation_blocked_local_readiness` only describes the local activation checklist; it does not execute provider samples, create tasks, or prove production completion.
- `provider_target_sample_acceptance_contract.status=target_sample_acceptance_ready_for_review` only means explicit target-domain sample evidence is reviewable for the selected target groups. It is not full-interface provider-backed acceptance, not production Tushare completion, and not evidence that GET cache or React render called a provider.
- Multi-target review-ready evidence is still not full-interface evidence: even when dragon-tiger, limit/emotion, chip distribution, financial disclosure, and hard-risk rows all reach `target_sample_acceptance_ready_for_review`, `provider_backed_acceptance_done=false`, `full_interface_acceptance_done=false`, and `production_tushare_pipeline_complete=false` must remain visible.
- `provider_target_sample_runbook_contract.status=target_sample_runbook_ready_provider_review_pending` only means the explicit provider-sample review checklist is complete for the requested target domains. It is not provider execution, provider-backed acceptance, full-interface acceptance, or production Tushare completion.
- The local Tushare acceptance push-gate contract is not a provider run; it only blocks regressions in button gating, matrix semantics, call-ledger requirements, pending provider acceptance flags, and no-trade/no-action boundaries.
- The `provider_backed_trade_cal_long_window` task mode is a controlled evidence marker for the `trade_cal` target only. It is not Tushare full-interface acceptance, not production pipeline completion, and not automatic provider execution.
- `live_light` bootstrap is not implemented yet. It still needs configuration, mode display, rate limiting, one-task-per-window dedupe, task status polling, safe failure display, and token-safe call ledger before it can be enabled.

### Implementation Phases

1. Validate `trade_cal` first because freshness depends on it.
2. Validate market evidence groups one at a time: margin, dragon-tiger, limit/emotion, chip, disclosure, hard risk.
3. Add per-interface request parameter contracts and safe error states.
4. Persist only production-approved datasets; keep other results as validation records until storage contracts are ready.
5. Add a future `live_light` bootstrap task that can refresh only current target / holdings / watchlist light data through POST task, with `daily`, `daily_basic`, `moneyflow`, and `trade_cal if needed` as the initial allowed interface set.

### Acceptance Criteria

- Every selected interface runs through POST task pipeline only.
- `cache_only` GET cache and React render never call Tushare directly.
- Future `live_light` refresh can only be created by a POST bootstrap task after initial cache render, with rate limit, dedupe, symbol limit, and visible mode state.
- Every interface records `call_ledger`, `row_count`, `data_date`, `local_fetched_at`, `call_status`, and `error_message_safe`.
- Permission denied, no record, empty window, parse failure, missing parameter, and blocked state are distinguishable.
- Unselected APIs never display as `verified`.
- `api_acceptance_audit.status=acceptance_audit_passed` only means call-ledger semantics are safe; `full_interface_acceptance_done` must remain false until all declared APIs are selected and provider-validated.
- `failure_mode_qa_contract` shows observed vs ready-not-observed failure modes without raw provider errors, stack traces, token, or key material.
- `request_parameter_qa_contract` shows declared params, provided safe params, missing required preflight params, date context fields, alias handling, and provider acceptance requirements without storing token/key material.
- `provider_acceptance_promotion_audit` shows whether prior evidence is strong enough to promote provider-backed acceptance, while the audit itself remains local/read-only and never calls Tushare.
- `provider_target_sample_plan_contract` shows each target domain's required APIs, sample window, request context, success evidence, failure evidence, and ready/pending/blocker state without calling provider APIs.
- `provider_evidence_gap_audit` shows each target domain's missing required APIs, missing call-ledger rows, non-empty sample gaps, failed/blocked evidence, failure-mode evidence gaps, target-sample acceptance review state, and promotion blockers while staying local/read-only and not provider acceptance.
- `provider_sample_readiness_receipt` shows ready target count, blocked target count, target-sample acceptance review count, allowed next step, forbidden shortcuts, missing evidence items, no-provider-call receipt boundary, and no-trade/no-action boundaries.
- `provider_sample_activation_receipt` shows readiness receipt visibility, explicit POST task requirement, provider execution evidence required, promotion review required, target gap ledger visibility, matrix/local QA not acceptance, cache/render no-provider boundary, production-completion boundary, and no-trade/no-action boundary.
- `provider_target_sample_acceptance_contract` shows explicit acceptance mode, requested target groups, target rows, sample sufficiency, failure-mode evidence, source-task call state, no contract-side provider calls, and full-interface/production-completion false flags.
- Local push-gate coverage includes a multi-target sample acceptance fixture where dragon-tiger, limit/emotion, chip distribution, financial disclosure, and hard-risk target groups can feed the gap ledger and readiness receipt as review-ready evidence only; every such row must still be blocked from provider promotion by `provider_promotion_not_ready`.
- `provider_target_sample_runbook_contract` shows target-domain POST route, required acceptance mode, required API selection, payload context, evidence checklist, promotion blockers, allowed next step, forbidden shortcuts, no-provider-call flags, and no-trade/no-action flags for single-target and multi-target sample review.
- `provider_acceptance_readiness_audit.provider_backed_acceptance_done=false` and `production_tushare_pipeline_complete=false` until real provider-backed full-interface acceptance is explicitly proven.
- `scripts/tushare_acceptance_contract.py` passes in the push gate while still reporting `provider_backed_acceptance_done=false`, `production_tushare_pipeline_complete=false`, and `full_interface_acceptance_done=false`.
- Tokens are never printed, stored in packets, or exposed to frontend.
- `trade_cal` provider-backed long-window evidence requires explicit payload, long-window schema evidence, freshness replay, and failure-mode validation; a plain successful `trade_cal` refresh remains a normal selected API result.
- Future live startup UI shows current mode, Tushare auto-refresh on/off, latest bootstrap task status, skipped-by-rate-limit state, and safe errors without exposing token/key.

### Forbidden

- Do not call Tushare from GET cache or page render.
- Do not treat a future React mounted POST bootstrap task as a direct render/provider call; keep the distinction explicit in tests and docs.
- Do not enable `live_light` by default; local users must opt in through config or an explicit UI mode.
- Do not mark matrix-only rows as real validation.
- Do not treat `api_acceptance_audit` as proof that provider coverage or production refresh is complete.
- Do not treat `failure_mode_qa_contract` as proof that permission-denied, empty-window, or parse-failure cases have all been observed against real Tushare.
- Do not treat `request_parameter_qa_contract` as proof that all interface windows, periods, or announcement dates are provider-accepted.
- Do not treat `provider_target_sample_plan_contract` or `ready_to_execute_provider_sample` rows as real provider-backed acceptance.
- Do not treat `provider_acceptance_readiness_audit` as production completion while it reports `provider_acceptance_pending`.
- Do not treat `provider_evidence_gap_audit` or cleared gap rows as provider-backed acceptance; it is a local evidence ledger and still requires explicit provider-backed promotion evidence.
- Do not treat `provider_sample_readiness_receipt.ready_for_explicit_provider_sample_task=true` as provider-backed acceptance; it only means the next safe step is an explicit POST task or promotion review.
- Do not treat `provider_sample_activation_receipt.local_activation_receipt_ready=true` as provider-backed acceptance, provider task execution, or production Tushare completion.
- Do not treat `provider_target_sample_acceptance_contract.target_sample_acceptance_ready_for_review=true` as full-interface acceptance, production Tushare completion, or evidence that cache/render paths called Tushare.
- Do not treat multi-target local review-ready evidence as full-interface provider-backed acceptance, production Tushare completion, or permission to retire matrix/gap/promotion blockers.
- Do not treat `provider_target_sample_runbook_contract.runbook_ready=true` as provider execution, provider-backed acceptance, full-interface acceptance, production Tushare completion, or permission to bypass explicit promotion audit.
- Do not treat `scripts/tushare_acceptance_contract.py` passing as real Tushare provider acceptance; it is only a local push-gate regression guard.
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
- GET factor cache now exposes `local_dataset_sample_evidence`: a local Parquet/DuckDB sufficiency audit for `factor_values`, `daily`, `daily_basic`, `moneyflow`, and `trade_cal`. It counts ticker/date/factor/usable-row readiness and forward-return label presence, but does not compute IC metrics, call providers, or prove real small-pool validation.
- Factor Test Lab packets now expose `small_pool_acceptance`: a local light-observation readiness audit for IC / Rank IC / ICIR, group return, cost, drawdown, neutral IC, sample split/decay, and PIT/lookahead/survivorship checks. This audit does not treat storage query rows as metric samples and does not prove real small-pool or full-market production validation.
- Factor Test Lab packets now expose `production_validation_qa_contract`: a local QA contract for future provider-backed small-pool validation, multi-horizon forward returns, rolling IC/ICIR, out-of-sample decay, production cost assumptions, neutralization stability, PIT/lookahead/survivorship controls, storage-query boundaries, research-only state transitions, and trade/action isolation. It does not run provider-backed samples, full-market research, external calls, or trade actions.
- Factor Test Lab packets now expose `provider_validation_blocker_audit`: a local read-only blocker summary for storage-query boundaries, local dataset sufficiency, local light metrics, provider-backed small-pool samples, multi-window validation, cost/neutralization/bias controls, full-market validation, and trade/action isolation.
- Factor Test Lab packets now expose `provider_sample_readiness_receipt`: a local read-only receipt that tells whether the next safe LTG-03 step is completing local dataset/forward-return evidence, running an explicit POST provider-backed small-pool acceptance task, or reviewing prior provider evidence. It does not call providers and keeps local light metrics, storage rows, QA rows, and blocker audits out of production validation promotion.
- Factor Test Lab packets now expose `provider_sample_activation_receipt`: a local activation checklist for the future explicit provider-backed small-pool validation task. It keeps provider task creation, provider call-ledger evidence, multi-horizon/rolling/cost/neutralization/bias evidence, explicit promotion marker, and production completion pending while confirming GET cache and React render do not call providers or mutate action.
- `scripts/factor_test_lab_contract.py` is now part of the local push gate. It uses synthetic local light observations and cache-only service contracts to keep Factor Test Lab metrics, small-pool readiness, storage-query consumption, and production QA clearly separated from provider-backed / full-market validation.

### Gaps

- No complete full-market or stock-pool validation.
- Multi-window, multi-horizon, out-of-sample, and factor decay validation are incomplete.
- Production-grade transaction cost assumptions are not validated.
- Industry and market-cap neutral stability needs larger samples.
- The research-state contract and DuckDB query consumption contract are local/light-mode governance and do not prove full-market validation.
- The local dataset sample evidence is only a sufficiency audit. It can report local Parquet availability or insufficiency, but it does not create forward-return labels, compute production metrics, or validate provider-backed samples.
- The small-pool acceptance audit is a local readiness contract; provider-backed small-pool samples are still pending.
- The production validation QA contract is visible, but all provider-backed / full-market production validation remains pending.
- The provider validation blocker audit is not provider execution; it only centralizes the remaining small-pool/full-market blockers and keeps production validation incomplete.
- The provider sample activation receipt is not provider execution; it only makes the final local checklist visible before a future explicit POST task. It cannot create tasks, call providers, promote local metrics, or mark production Factor Test validation complete.
- The local Factor Test Lab push-gate contract is not a provider run; it only blocks regressions where local light metrics, storage query rows, or QA checklist rows are mistaken for production validation.

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
- `local_dataset_sample_evidence` remains cache-only/read-only, reports ticker/date/usable-row/forward-return sufficiency, keeps `metrics_computed_from_local_dataset=false`, and keeps `provider_backed_small_pool_validation_done=false`.
- `small_pool_acceptance.status=local_small_pool_acceptance_ready` only means local light observations satisfy the readiness checklist; `real_small_pool_validation_done` and `full_market_validation_done` must remain false until provider-backed samples are validated.
- `production_validation_qa_contract.production_factor_test_validation_complete=false` until provider-backed small-pool samples, multi-horizon/rolling-window validation, cost assumptions, neutralization stability, bias controls, and trade/action isolation are all verified.
- `provider_validation_blocker_audit.status=provider_validation_blockers_visible` keeps provider-backed sample, full-market, multi-window, cost/neutralization/bias, and sample-sufficiency blockers visible without calling providers or computing production metrics.
- `provider_sample_readiness_receipt.status` may be `provider_small_pool_receipt_blocked_local_sample_or_contract`, `provider_small_pool_receipt_ready_execution_pending`, or `provider_small_pool_receipt_ready_for_promotion_review`. Only the middle state allows a future explicit POST small-pool provider acceptance task; no state calls a provider or proves production completion by itself.
- `provider_sample_activation_receipt` shows readiness receipt visibility, explicit POST task requirement, provider execution evidence requirement, production QA visibility, provider blocker visibility, local-metrics-not-acceptance boundary, cache/render no-provider boundary, production-completion boundary, and trade/action isolation.
- `scripts/factor_test_lab_contract.py` passes in the push gate while still reporting `provider_backed_small_pool_validation_done=false`, `full_market_validation_done=false`, and `production_factor_test_validation_complete=false`.

### Forbidden

- Do not present research metrics as trading advice.
- Do not promote `research_pass` to action without separate approval.
- Do not compute action in frontend.
- Do not treat storage query consumption as real small-pool, full-market, or production factor validation.
- Do not treat `local_dataset_sample_evidence` as real Factor Test validation; it is a local sample sufficiency audit and may remain blocked when rows, tickers, forward returns, or provider-backed samples are insufficient.
- Do not treat local small-pool readiness as real provider-backed production validation.
- Do not treat `production_validation_qa_contract` as execution evidence; it is a QA checklist until future button/task validation proves the rows.
- Do not treat `provider_validation_blocker_audit.provider_validation_ready=true` as production completion; it only means local blocker rows are clear enough for promotion review.
- Do not treat `provider_sample_readiness_receipt.ready_for_explicit_provider_small_pool_task=true` as provider-backed validation; it only means the next safe step is a user-triggered POST task. When it is blocked, complete local dataset sample depth and forward-return evidence first.
- Do not treat `provider_sample_activation_receipt.local_activation_receipt_ready=true` as provider-backed validation, task execution, or production Factor Test completion.
- Do not treat `scripts/factor_test_lab_contract.py` passing as real Factor Test Lab production validation; it is only a local research-boundary regression guard.

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
- Factor Quant Hub now exposes `universe_local_rank_zscore_dry_run`, a local `factor_values` cross-section sufficiency and optional preview audit. It may preview rank/zscore only when enough local tickers exist per trade-date/factor group, keeps the preview research-only, and never marks full-pool/provider-backed production research complete.
- Factor Quant Hub now exposes `universe_execution_readiness_receipt`: a local read-only receipt that says whether LTG-04 is blocked on read-plan/storage contracts, ready for a future explicit worker-batch research task, or ready for promotion evidence review. It never runs full-pool research, production rank/zscore, neutralization, provider validation, or trades.
- Factor Quant Hub now exposes `universe_execution_activation_receipt`: a local activation receipt that fixes the next safe LTG-04 step as an explicit worker-batch production validation task while keeping worker creation, worker execution, production rank/zscore, neutralization, factor-combination research, full-pool/provider validation, provider/model/GitHub calls, and trading actions false.
- `scripts/factor_universe_contract.py` is now part of the local push gate. It validates LTG-04 universe modes, local storage read-plan consumption, task catalog button gating, React read-only display, partial-pool-not-full-market-proof visibility, no batch execution, no provider/model/GitHub calls, no trades, and no action mutation while `production_factor_universe_complete=false`.

### Gaps

- Full-market universe is incomplete.
- Industry and market-cap neutral full-sample validation is incomplete.
- Factor combination research is incomplete.
- The universe read plan does not perform watchlist/custom/full-pool batch research yet.
- Cross-sectional rank, zscore, neutralization, result summaries, and worker-backed large-universe execution are still incomplete.
- Local rank/zscore dry-run may remain blocked when local `factor_values` lacks enough usable tickers per trade-date/factor group; this is a sufficiency audit, not production execution.
- `universe_execution_readiness_audit.status=read_plan_ready_execution_pending` only proves the local read-plan contract after the button task; it is not provider-backed full-market research and keeps production blockers visible.
- `universe_execution_readiness_receipt.status=universe_execution_receipt_ready_worker_batch_pending` only means the read-plan/storage/worker-consumption boundary is ready for a future explicit worker-batch task. It does not execute that task and does not clear rank/zscore, neutralization, full-pool validation, or production completion blockers.
- `universe_execution_activation_receipt.status=universe_execution_activation_ready_worker_batch_pending` only fixes the next explicit worker-batch validation gate. It does not create a task, start a worker, compute production rank/zscore, run neutralization, validate full-pool/provider evidence, or promote production completion.
- The Factor universe push-gate contract is local only; it does not run worker-backed batch research, rank/zscore, neutralization, provider-backed validation, factor combination research, or full-pool production research.

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
- `universe_local_rank_zscore_dry_run` remains cache-only/read-only, keeps `metrics_are_research_only=true`, `frontend_computes_rank_zscore=false`, `cross_sectional_rank_zscore_done=false`, and `production_factor_universe_complete=false`.
- `universe_execution_readiness_audit.production_factor_universe_complete=false` until worker-backed batch execution, rank/zscore, neutralization, result summaries, and full-pool/provider-backed validation are implemented and verified.
- `universe_execution_readiness_receipt.ready_for_explicit_worker_batch_task=true` only after a button-gated read-plan exists, storage query contracts are consumed, worker consumption plan is visible, frontend remains read-only, and trade/action isolation holds.
- `universe_execution_activation_receipt.local_activation_receipt_ready=true` only after the readiness receipt, read plan, storage contracts, worker-consumption plan, frontend read-only boundary, and trade/action isolation are all visible; it must still report `worker_batch_executed_by_receipt=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `full_pool_validation_done=false`, and `production_factor_universe_complete=false`.
- `scripts/factor_universe_contract.py` passes in the local push gate while reporting `large_universe_pipeline_done=false`, `full_pool_validation_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, and `production_factor_universe_complete=false`.

### Forbidden

- Do not block page render with full-pool computation.
- Do not write universe data to git.
- Do not treat partial universe samples as full-market proof.
- Do not treat `universe_local_rank_zscore_dry_run` as real full-pool research, provider-backed validation, or trading evidence.
- Do not treat `universe_execution_readiness_audit` as production factor-universe completion while it reports execution pending.
- Do not treat `universe_execution_readiness_receipt.ready_for_explicit_worker_batch_task=true` as worker-backed batch execution or full-pool research completion; it only identifies the next explicit task gate.
- Do not treat `universe_execution_activation_receipt.local_activation_receipt_ready=true` as worker-backed batch execution, production rank/zscore, neutralization, provider-backed validation, full-pool completion, or production Factor universe completion.
- Do not treat `scripts/factor_universe_contract.py` passing as worker-backed batch execution, rank/zscore, neutralization, provider-backed validation, factor combination research, full-pool research, or production Factor universe completion.

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
- Storage overview/catalog and the cleanup dry-run packet now expose `command_center_3_storage_artifact_cleanup_review_contract.v1`: a path-only manual review contract with required review steps, no delete execution, no generated delete command, no payload reads, no secret-value scan, no external calls, no trades, and no `strategy action` mutation.
- Storage overview and catalog now expose a metadata-only schema migration preflight for all canonical datasets: target schema version, required columns, primary key, partition expectation, current parquet status, and manual migration boundaries are visible without reading payloads or writing Parquet.
- Storage overview and catalog now expose a cache-only dataset version policy matrix: declared dataset version, manifest path, physical validation boundary, and no-write-on-GET guarantees are visible before any production manifest writer exists.
- Storage overview and catalog now expose `dataset_version_manifest_evidence_audit`: a read-only local `_dataset_versions.json` evidence check that reports missing / mismatch / validated rows without writing a manifest, reading Parquet payloads, calling providers, or claiming production storage completion.
- `POST /api/storage/dataset-version-manifest/dry-run` now creates a button-gated local task and packet that proposes `_dataset_versions.json` entries from canonical schema contracts without writing the manifest, reading Parquet row payloads, writing Parquet, calling providers, or claiming production storage completion.
- `POST /api/storage/dataset-version-manifest/review` now creates a button-gated local review task and packet that compares manifest dry-run rows with schema acceptance rows before any write. It records schema blockers, approved-for-write rows, and production promotion blockers without writing `_dataset_versions.json`, writing Parquet, reading row payloads, calling providers, or claiming production storage completion.
- `POST /api/storage/dataset-version-manifest/write` now creates or updates the local ignored `_dataset_versions.json` only after explicit confirmation, then reuses the read-only evidence audit to verify manifest rows. It does not write Parquet, read Parquet row payloads, call providers, execute trades, or mark production storage complete.
- `POST /api/storage/dataset-version-manifest/validate` now creates a button-gated local validation task and packet that reads only the local ignored `_dataset_versions.json` evidence after a manual write. It reports validated/blocked manifest rows, but does not write the manifest, write Parquet, read Parquet row payloads, execute schema/partition/compaction/TTL tasks, call providers, execute trades, or mark production storage complete.
- Dataset version manifest evidence, dry-run, write, and validate packets now expose safe SHA-256 content fingerprints. The write packet records the dry-run proposed hash, written payload hash, post-write readback hash, and a readback-match flag without printing raw secret-bearing content, reading Parquet payloads, calling providers, or claiming production storage completion.
- `POST /api/storage/schema-validation/dry-run` now creates a local task and packet that reads Parquet schema metadata only, compares physical columns with canonical schema contracts, and reports `schema_validated` / `schema_mismatch` / `missing_dataset` before any migration.
- `POST /api/storage/schema-validation/acceptance` now records button-gated physical schema metadata acceptance rows for local Parquet datasets. It can mark individual datasets as accepted for later manifest promotion / partition migration, but still does not write Parquet, read row payloads, execute migration, call providers, or mark production storage complete.
- `POST /api/storage/partition-migration/dry-run` now creates a local task and packet that builds per-dataset partition migration plans from schema validation and partition contracts, without reading row payloads or writing partitioned Parquet.
- `POST /api/storage/compaction/dry-run` now creates a local task and packet that lists Parquet compaction ready/not-needed/missing rows without reading row payloads or rewriting Parquet.
- `POST /api/storage/cache-ttl/dry-run` now creates a local task and packet that lists fresh/stale/missing TTL states and refresh recommendations without refreshing providers or writing Parquet.
- DuckDB query service policy is visible in storage overview/catalog: canonical dataset paths, supported filters, limit guard, safe parameter binding, and frontend no-direct-DataFrame boundaries are auditable.
- DuckDB dataset reads now return typed projection columns, `duckdb_query_result_contract.v1`, and offset cursor `page_info` for local Parquet reads.
- React Storage now exposes read-only DuckDB cursor controls that pass `page_info.next_cursor` back through FastAPI GET storage APIs; the controls do not refresh providers, write Parquet, or read DataFrames directly.
- React Storage now exposes read-only dataset filters for `limit`, `ts_code`, `trade_date`, `start_date`, and `end_date`; applying filters resets to the first page and still routes only through GET storage APIs.
- Factor Universe now has a button-gated local read-plan task that consumes storage query contracts and records dataset-level projection/page metadata for future worker consumption.
- Storage overview/catalog now expose `storage_production_blocker_audit`: production remains `storage_production_blocked` until physical schema validation, schema migration, dataset version manifest validation, partition migration, physical compaction, and TTL refresh execution are separately implemented.
- Storage overview/catalog now expose `storage_production_readiness_receipt`: a local next-step receipt that says LTG-05 is ready for explicit POST schema/manifest review tasks while keeping GET migration, provider refresh, automatic compaction, TTL refresh execution, cleanup delete execution, and production-completion claims forbidden.
- Storage overview/catalog now expose `storage_physical_migration_activation_receipt`: a local activation receipt that links the next explicit schema acceptance, manifest validation, partition, compaction, TTL, cleanup, and promotion prerequisites while keeping all physical writes, provider refreshes, delete execution, trades, and production-completion claims pending.
- `scripts/storage_contract.py` is now part of the local push gate. It reads only local storage cache and dry-run packet builders, then verifies schema migration preflight, dataset version policy, schema validation dry-run, partition migration dry-run, compaction dry-run, cache TTL dry-run, artifact cleanup review, DuckDB query service, and storage dry-run task gating remain local/no-write/no-provider/no-trade while `production_storage_complete=false`.

### Gaps

- Production schema migration execution.
- Physical dataset version manifest promotion beyond the local-only manifest writer and local-only manifest validation packet.
- Manifest writer and validator are button-gated and local-only, but reviewer approval workflow, schema acceptance promotion rules, physical migration rules, and production promotion rules remain pending.
- Manifest validation currently proves local schema contract version rows in `_dataset_versions.json`, not physical Parquet schema compatibility, schema migration, partition migration, compaction, TTL refresh, or production dataset migration completion.
- Physical partition migration execution.
- Physical compaction execution beyond the button-gated dry-run.
- Physical refresh scheduling/execution beyond the button-gated cache TTL dry-run.
- Real large-universe research execution beyond the local Factor Universe read plan.
- Full-pool research consumption, richer query result contract hardening beyond the current local DuckDB read path, and production-grade query ergonomics beyond the current basic UI filters.
- Physical cleanup/delete execution after manual review remains unimplemented and must stay separately approved.
- `storage_production_readiness_receipt.status=storage_readiness_receipt_ready_physical_migration_pending` is expected while production blockers remain; it is a next-step receipt, not production storage completion.
- `storage_physical_migration_activation_receipt.status=storage_physical_migration_activation_receipt_ready_execution_pending` is expected while physical execution evidence is missing; it is an activation checklist, not schema migration, partition migration, compaction, TTL refresh, cleanup delete, or production promotion evidence.
- The local Storage push-gate contract is not a physical migration or production data-layer proof; it only blocks regressions where preflights, dry-runs, query policy, or cleanup review could be mistaken for production completion.

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
- `dataset_version_manifest_evidence_audit` remains cache-only and read-only: when `_dataset_versions.json` is missing it reports `manifest_missing_validation_pending`; when a local manifest exists it can report local version matches, but still keeps `manifest_written_on_get=false`, `cache_get_writes_files=false`, `cache_get_reads_parquet_payloads=false`, and `dataset_version_migration_executed_count=0`.
- Dataset version manifest dry-run is button-gated, creates only a local task/packet, proposes manifest rows, keeps `manifest_write_executed=false`, `post_dry_run_writes_manifest=false`, `post_dry_run_writes_parquet=false`, `post_dry_run_reads_parquet_payloads=false`, and requires a separate approved writer before any `_dataset_versions.json` change.
- Dataset version manifest hash evidence is audit-only: missing manifests keep an empty hash; present manifests expose `manifest_hash_algorithm=sha256`, a 64-character content hash, sorted dataset keys, and no raw payload leakage in the UI summary.
- Dataset version manifest review is button-gated, creates only a local task/packet, compares dry-run and schema acceptance rows, keeps `manifest_write_executed=false`, `post_review_writes_manifest=false`, `post_review_writes_parquet=false`, `post_review_reads_parquet_payloads=false`, `dataset_version_manifest_validated=false`, and requires a separate approved writer plus separate production promotion before any completion claim.
- Dataset version manifest write is button-gated, requires `confirm_manifest_write=true`, writes only `_dataset_versions.json`, keeps `writes_parquet=false`, `reads_parquet_payloads=false`, `external_calls_triggered=false`, and still keeps `production_storage_complete=false`.
- Dataset version manifest validate is button-gated, reads only local manifest evidence, keeps `manifest_write_executed=false`, `post_validate_writes_manifest=false`, `post_validate_writes_parquet=false`, `post_validate_reads_parquet_payloads=false`, `schema_migration_executed=false`, `partition_migration_executed=false`, `physical_compaction_executed=false`, `cache_ttl_refresh_executed=false`, and still keeps `production_storage_complete=false`.
- Schema validation dry-run is button-gated, reads no row payload, writes no Parquet, and records missing/mismatch/validated rows before any migration.
- Schema validation acceptance is button-gated, reads only Parquet schema metadata, writes only a local SQLite packet, keeps `post_acceptance_writes_parquet=false`, `post_acceptance_reads_row_payloads=false`, `schema_migration_executed=false`, and still keeps `production_storage_complete=false`.
- Partition migration dry-run is button-gated, writes no partitioned Parquet, and records ready/blocked/missing rows before any partition writer task.
- Compaction dry-run is button-gated, writes no Parquet, reads no row payload, and records ready/not-needed/missing rows before any physical compaction task.
- Cache TTL dry-run is button-gated, calls no providers, writes no Parquet, and records fresh/stale/missing refresh recommendations before any refresh task.
- DuckDB query service remains local/canonical-path-only, uses safe parameter binding and limit guards, and is visible to React as a policy matrix; React does not query Parquet or hold large DataFrames directly.
- DuckDB query results expose projection columns, missing projection columns, order columns, `page_info`, and `next_cursor`; these remain read-only local contracts and do not refresh data.
- React cursor controls use only GET storage API cursor parameters, can reset to the first page, and preserve the no-provider-refresh / no-Parquet-write / no-trade-action boundary.
- React dataset filters use only GET storage API query parameters, keep cursor pagination local and read-only, and preserve the no-provider-refresh / no-Parquet-write / no-trade-action boundary.
- Generated artifact hygiene is auditable; dry-run cleanup is button-gated and any real delete/cleanup must remain separate and manually approved.
- Artifact cleanup manual review is visible as a contract after dry-run, with `delete_executed=false`, `safe_delete_command_generated=false`, and `production_cleanup_complete=false`.
- Storage overview/catalog now expose `storage_production_blocker_audit` and `storage_production_blocker_rows`, explicitly separating local contracts/dry-runs/preflights from physical production completion.
- Storage overview/catalog expose `storage_production_readiness_receipt` and receipt rows showing `local_receipt_ready=true`, `allowed_next_step=explicit_post_task_storage_schema_acceptance_manifest_review`, forbidden shortcuts, no provider refresh, no cache GET external calls, no Parquet writes from the receipt, no cleanup deletes, no trades, no `strategy action` mutation, and `production_storage_complete=false`.
- Storage overview/catalog expose `storage_physical_migration_activation_receipt` and activation rows showing `local_activation_receipt_ready=true`, `allowed_next_step=explicit_schema_acceptance_manifest_validate_then_partition_compaction_ttl_cleanup_reviews`, missing physical schema/manifest/partition/compaction/TTL/cleanup/promotion evidence, no GET migration, no GET Parquet write, no provider refresh, no generated cleanup delete, no trades, no `strategy action` mutation, and `production_storage_complete=false`.
- `scripts/storage_contract.py` passes in the push gate while still reporting `production_storage_complete=false`, `physical_schema_validation_done=false`, `schema_migration_executed=false`, `dataset_version_manifest_validated=false`, `partition_migration_executed=false`, `physical_compaction_executed=false`, `cache_ttl_refresh_executed=false`, and `artifact_cleanup_delete_executed=false`; it also verifies manifest evidence remains read-only and no-writer/no-payload.
- `scripts/storage_contract.py` now verifies manifest hash evidence stays local and safe: dry-run proposed manifests must include a SHA-256 fingerprint, and read-only evidence must either expose a valid SHA-256 hash for an existing local manifest or remain empty when the manifest is missing.
- Write failure does not pollute packet or action.

### Forbidden

- Do not write Parquet from GET cache.
- Do not treat schema migration preflight as physical validation or production migration completion.
- Do not treat dataset version manifest dry-run as a manifest writer, manifest validation, physical migration, or production storage completion.
- Do not treat dataset version manifest review as a manifest writer, manifest validation, physical migration, production promotion, or production storage completion.
- Do not treat dataset version manifest write as physical Parquet validation, schema migration, partition migration, or production storage completion.
- Do not treat dataset version manifest validate as a manifest writer, physical Parquet validation, schema migration, partition migration, compaction, TTL refresh, production promotion, or production storage completion.
- Do not treat manifest SHA-256 evidence as data validation, provider acceptance, physical migration, production promotion, or proof that Parquet payloads are correct; it only proves local manifest payload identity/readback.
- Do not treat dataset version policy as physical dataset version validation or manifest migration completion.
- Do not treat `dataset_version_manifest_evidence_audit` as a manifest writer, physical dataset migration, or production dataset version completion; it is local evidence only.
- Do not treat schema validation dry-run as production schema migration completion.
- Do not treat partition migration dry-run as physical partition migration completion.
- Do not treat compaction dry-run as physical Parquet compaction completion.
- Do not treat cache TTL dry-run as data refresh completion or provider acceptance.
- Do not treat artifact cleanup review as delete execution or production cleanup completion.
- Do not treat `storage_production_readiness_receipt` as physical migration, provider refresh, automatic compaction, cleanup execution, or production storage completion; it only permits the next explicit POST review task.
- Do not treat `storage_physical_migration_activation_receipt` as schema validation acceptance, manifest validation, physical migration, provider refresh, compaction execution, TTL refresh execution, cleanup delete execution, production promotion, or production storage completion; it only names the next explicit execution prerequisites.
- Do not treat `scripts/storage_contract.py` passing as physical schema validation, schema migration, dataset version manifest validation, partition migration, physical compaction, TTL refresh execution, cleanup delete execution, or production storage completion.
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
- Worker runtime now exposes `worker_task_log_persistence_audit`: a cache-only local audit that proves safe `task_log` metadata is visible through the task status index and memory/SQLite fallback summary. It keeps `task_log_persistence_verified=false`, `append_only_worker_log_verified=false`, `cross_process_log_round_trip_verified=false`, `healthcheck_executed=false`, and `production_worker_complete=false`; it does not read raw task payloads, write logs, start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, or execute trades.
- Worker runtime now exposes `worker_queue_routing_contract`: a local future-Celery routing contract that classifies tasks into `provider_refresh`, `model_explain`, `external_probe`, `local_maintenance`, and `local_compute`, keeps provider/model/probe-capable tasks out of local queues, keeps all queues button-gated, and keeps scheduler/cache dispatch disabled. It does not start Celery, ping Redis, dispatch tasks, call providers/models/probes, execute trades, or prove production worker completion.
- Worker runtime now supports explicit `POST /api/worker/synthetic-healthcheck`: a button-gated local synthetic task that creates a local task, marks it success, reads it back through task status, verifies safe `task_log` visibility, writes `command_center_3_worker_synthetic_healthcheck_packet`, and then lets GET cache display the last result. It also records SHA-256 fingerprints for safe task identity/readback fields, so the local task/status/log round trip can be checked without printing raw payloads. It does not start Celery, ping Redis, start scheduler, validate cross-process controls, call Tushare/DeepSeek/GitHub, execute trades, or mark `production_worker_complete=true`.
- Worker runtime now exposes `worker_activation_review_contract`: a manual activation review contract for production worker enablement. It lists production blocker review, Redis broker configuration, Celery manual start, synthetic healthcheck, cross-process controls, task log persistence, scheduler default-off, provider/model isolation, local fallback rollback, and secret redaction. It keeps `activation_ready=false` and `production_worker_complete=false`; it does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, or execute trades.
- Worker runtime now exposes `worker_production_readiness_receipt`: a local next-step receipt that ties blocker audit, healthcheck QA, task-log audit, synthetic healthcheck state, activation review, and route coverage into one explicit LTG-06 checkpoint. It can mark `ready_for_explicit_synthetic_healthcheck=true`, but keeps `ready_for_manual_activation_review=false` while production blockers remain and keeps `production_worker_complete=false`, `worker_started_by_receipt=false`, `redis_pinged_by_receipt=false`, `scheduler_started_by_receipt=false`, and `task_dispatched_by_receipt=false`.
- Worker runtime now exposes `worker_production_activation_receipt`: a local production-start checklist that ties readiness receipt, synthetic healthcheck state, Celery manual start, Redis broker reachability, cross-process controls, append-only logs, scheduler default-off, provider/model isolation, manual activation approval, and production promotion evidence into one activation layer. It keeps `worker_activation_receipt_ready_production_blocked`, `activation_ready=false`, `production_worker_complete=false`, `worker_started_by_receipt=false`, `redis_pinged_by_receipt=false`, `scheduler_started_by_receipt=false`, and `task_dispatched_by_receipt=false`.
- `scripts/worker_contract.py` is now part of the local push gate. It validates worker cache, dispatch plan, production blocker audit, healthcheck QA, task-log persistence audit, synthetic healthcheck explicit-POST boundary, activation review, readiness receipt, scheduler default-off, no-external-call, no-provider-call, no-trade, and no-action boundaries while `production_worker_complete=false`.
- Celery/Redis are not production enabled.

### Gaps

- Real Celery worker.
- Redis broker.
- Task retry execution.
- Task cancellation semantics across worker process.
- Concurrency locks.
- Append-only worker log persistence and cross-process log round-trip proof.
- Live Celery route binding, Redis broker queue declaration, worker process queue consumption, and queue-specific runtime evidence remain pending after the local queue routing contract.
- Scheduler production config.
- The Worker push-gate contract is still a local guard only; real Celery/Redis process startup, broker reachability, cross-process controls, append-only worker log proof, and scheduler production enablement remain pending.
- The explicit synthetic healthcheck proves only local fallback task/status/log round trip. Its SHA-256 fingerprints prove safe local task identity/readback consistency only. It is useful evidence for the local control plane, but it is not Celery/Redis process proof and not production worker activation.
- The worker production readiness receipt is still a local next-step receipt. It does not start Celery, ping Redis, run healthcheck, start scheduler, dispatch tasks, or prove production worker completion.
- The worker production activation receipt is still a local checklist. It does not start Celery, ping Redis, run healthcheck, start scheduler, dispatch tasks, prove manual activation approval, or prove production worker completion.

### Implementation Phases

1. Keep local fallback stable.
2. Keep the dispatch plan matrix current as tasks are added, so future Celery/Redis routing has an auditable contract before execution is enabled.
3. Keep `worker_queue_routing_contract` current so provider/model/probe queues stay isolated from local queues before Celery routing is enabled.
4. Keep `worker_healthcheck_qa_contract` current so the future worker healthcheck has an explicit acceptance checklist before execution is enabled.
5. Keep `worker_task_log_persistence_audit` current so local safe task-log visibility is traceable while append-only/cross-process worker log proof remains pending.
6. Keep `POST /api/worker/synthetic-healthcheck` button-gated and local-only so task/status/log round-trip evidence remains visible before Celery/Redis activation.
7. Keep `worker_production_readiness_receipt` current so the next safe step is visible without converting local contracts into production completion evidence.
8. Keep `worker_production_activation_receipt` current so production-start blockers remain visible without starting processes.
9. Add Celery worker execution behind explicit configuration.
10. Add Redis broker configuration and health reporting without cache API pinging Redis.
11. Add retry/cancel/lock behavior for real worker tasks.
12. Keep scheduler default off.

### Acceptance Criteria

- POST task returns `task_id`.
- React polls task status.
- Worker executes heavy tasks.
- Redis absence gracefully falls back or reports clear blocker.
- Worker not started state is visible in UI.
- Production blocker rows are visible in UI, and `production_worker_complete` remains false until a future explicit worker health check proves Celery/Redis startup outside GET cache.
- Worker healthcheck QA rows are visible in UI, and `healthcheck_executed` remains false until a future synthetic/local worker healthcheck is explicitly run.
- Worker synthetic healthcheck can be run only by explicit POST/button; it creates a local task, verifies local task/status/log readback, exposes `healthcheck_hash_algorithm=sha256`, 64-character task/readback fingerprints, `task_readback_hash_matches=true`, displays the last result in GET cache, and still keeps `production_worker_complete=false`, `celery_worker_started=false`, `redis_pinged=false`, and `scheduler_started=false`.
- Worker task-log persistence rows are visible in UI, and `task_log_persistence_verified=false`, `append_only_worker_log_verified=false`, `cross_process_log_round_trip_verified=false`, and `production_worker_complete=false` until a future explicit live worker healthcheck proves append-only/cross-process log persistence.
- Worker queue routing rows are visible in UI, queue names include `provider_refresh`, `model_explain`, `external_probe`, `local_maintenance`, and `local_compute`, provider/model/probe-capable tasks do not enter local queues, all queues remain button-gated, scheduler auto task count is zero, and `production_worker_complete=false`.
- Worker activation review rows are visible in UI, and `activation_ready=false` until production blockers are resolved and an explicit synthetic/local worker healthcheck proves readiness.
- Worker readiness receipt rows are visible in UI, `allowed_next_step=explicit_post_worker_synthetic_healthcheck_then_manual_activation_review`, and `not_allowed_next_steps` explicitly blocks GET cache process start, Redis ping, scheduler start, task dispatch, unconfigured provider/model scheduling, and treating the receipt or synthetic healthcheck as production completion.
- Worker production activation receipt rows are visible in UI, `allowed_next_step=explicit_synthetic_healthcheck_then_manual_celery_redis_activation_review`, and `not_allowed_next_steps` explicitly blocks GET cache process start, Redis ping, scheduler start, task dispatch, unconfigured provider/model scheduling, and treating the activation receipt as production worker completion.
- `scripts/worker_contract.py` passes in the local push gate while reporting `production_worker_complete=false`, `healthcheck_executed=false`, `task_log_persistence_verified=false`, `append_only_worker_log_verified=false`, `activation_ready=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, `worker_queue_routing_contract_ready=true`, `worker_production_readiness_receipt_ready=true`, and `worker_production_activation_receipt_ready=true`.
- Production scheduler-based Tushare/DeepSeek scheduling is never automatic by default; future `live_light` may create only an opt-in, rate-limited POST bootstrap task.
- Failures include `error_message_safe`.

### Forbidden

- Do not start Celery, Redis, or scheduler from GET cache.
- Do not auto-schedule real provider/model tasks from GET cache, worker readiness receipts, or production scheduler defaults.
- Do not report preflight as production worker completion.
- Do not report blocker audit as production worker completion.
- Do not report local task-log persistence audit as append-only Celery/Redis worker log proof, cross-process worker round-trip proof, or production worker completion.
- Do not report `worker_queue_routing_contract` as Celery route binding, Redis broker queue declaration, worker process queue consumption, scheduler production enablement, provider/model task execution, or production worker completion.
- Do not report explicit synthetic healthcheck as Celery/Redis process proof, broker reachability, cross-process control proof, append-only worker log proof, scheduler production config, or production worker completion.
- Do not report worker synthetic healthcheck SHA-256 fingerprints as Celery/Redis process proof, broker reachability, cross-process control proof, append-only worker log proof, scheduler production config, provider/model validation, or production worker completion.
- Do not report activation review as worker startup, healthcheck execution, or production worker completion.
- Do not report `worker_production_readiness_receipt` as worker startup, Redis reachability, scheduler startup, task dispatch, healthcheck execution, activation approval, or production worker completion.
- Do not report `worker_production_activation_receipt` as synthetic healthcheck execution, Celery worker startup, Redis reachability, scheduler startup, task dispatch, manual activation approval, provider/model scheduling evidence, or production worker completion.
- Do not report `scripts/worker_contract.py` passing as Celery/Redis worker startup, broker health, synthetic healthcheck execution, cross-process task controls, scheduler production config, or production worker completion.

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
- Factor Quant Hub now exposes `deepseek_response_format_review_contract`: a local response-format / retry-repair review contract that verifies JSON-object prompt instruction, six whitelisted top-level fields, parse-failure discard behavior, illegal-field sanitization, no numeric/action overwrite, token budget visibility, GET/render no-model-call boundaries, and default-off auto-after-task governance. It keeps provider-level response format enforcement, bounded retry/repair policy, larger benchmark, and production automation blocked.
- Factor Quant Hub now exposes `deepseek_production_activation_receipt` and rows: a local LTG-07 next-step receipt that ties manual/default-off governance, sanitizer whitelist, JSON stability audit, response-format review, provider benchmark blockers, provider response_format blockers, bounded retry/repair blockers, token/cost evidence, auto_after_task activation, no GET/render model call, and no numeric/action overwrite into one checklist. It keeps `production_deepseek_explanation_complete=false`.
- `scripts/deepseek_governance_contract.py` is now part of the local push gate. It validates manual/default-off governance, sanitizer whitelist behavior, parse-failed discard, JSON stability blockers, response-format review blockers, button-gated task catalog, centralized model strategy, no-model-call, no-secret, no-trade, and no-action boundaries while production automatic explanation remains pending.
- Current state is suitable for manual explanation, not automatic production calling.
- Runtime mode policy now separates default safety from future local automation: `cache_only` never calls DeepSeek, `manual` calls only by explicit button/task, and future `live_light` may enqueue at most one governed DeepSeek pro explanation after Tushare/factor/next-session cache is ready.

### Gaps

- JSON success rate is not high enough.
- Larger benchmark is missing.
- Response format enforcement is incomplete.
- Token budget strategy is incomplete.
- `auto_after_task` needs conservative production governance.
- `deepseek_json_stability_audit.status=manual_ready_production_blocked` is a local sanitizer/prompt contract, not a real model benchmark pass.
- `deepseek_response_format_review_contract.status=response_format_review_ready_provider_enforcement_pending` is a local review contract; it does not prove provider-level response format enforcement, retry/repair execution, or larger benchmark success.
- `deepseek_production_activation_receipt.status=deepseek_activation_receipt_ready_provider_benchmark_pending` is a local activation receipt; it does not call DeepSeek, does not prove provider benchmark, does not enforce provider response_format, does not prove bounded retry/repair, and does not make `auto_after_task` production-ready.
- The DeepSeek governance push-gate contract is still a local guard only; provider-backed benchmark, provider response-format enforcement, bounded retry/repair execution, and production auto-after-task readiness remain pending.
- `live_light` DeepSeek is not implemented yet. It needs explicit config, mode display, input hash dedupe, model ledger, token budget display, safe retry/parse fallback, and rate limits before it can run automatically.

### Implementation Phases

1. Expand benchmark set with representative packets.
2. Tighten response format and retry/repair policy.
3. Track token budget and model choice per purpose.
4. Keep automatic explanation disabled unless explicitly enabled and bounded.
5. Promote `deepseek_json_stability_audit` from local readiness to real benchmark evidence only after provider-backed samples meet the target.
6. Add future `live_light` DeepSeek after-task behavior only after data tasks complete, with same-input hash dedupe and sanitizer-first writeback.

### Acceptance Criteria

- JSON success rate > 90%.
- No illegal fields.
- No trading action leakage.
- No numeric overwrite.
- Token cost is predictable and auditable.
- Failure does not pollute local results.
- `deepseek_json_stability_audit` must show `production_ready=true` only after JSON success rate exceeds 90%, larger benchmark is complete, and response format is enforced.
- `deepseek_response_format_review_contract` must keep `production_ready=false` until provider-level response format enforcement, bounded retry/repair policy, and larger benchmark evidence are all proven.
- `deepseek_production_activation_receipt` must keep `provider_benchmark_done=false`, `provider_response_format_enforced=false`, `bounded_retry_repair_ready=false`, `token_budget_cost_evidence_complete=false`, `auto_after_task_production_ready=false`, and `production_deepseek_explanation_complete=false` until the explicit provider-backed acceptance sequence is complete.
- `scripts/deepseek_governance_contract.py` passes in the local push gate while reporting `provider_benchmark_done=false`, `response_format_enforced=false`, `retry_repair_policy_ready=false`, `auto_after_task_production_ready=false`, `deepseek_production_activation_receipt_ready=true`, and `production_deepseek_explanation_complete=false`.
- GET cache and React render must keep `model_call_status=not_called`.
- Future `live_light` DeepSeek may only run through POST task / worker after data readiness, must record model used, status, token usage, parse status, cache hit/miss, input hash, and output hash, and must keep failed parse out of the packet.

### Forbidden

- Do not call DeepSeek on page render or GET cache.
- Do not treat future `live_light` after-task DeepSeek as a render call; it must remain a task with dedupe, mode gating, and audit fields.
- Do not enable DeepSeek `live_light` by default before benchmark, response-format, retry/repair, and token budget gates are accepted.
- Do not use DeepSeek as a data source.
- Do not let model output overwrite prices, positions, factor values, operation zones, or action.
- Do not treat local sanitizer/prompt audit as production automatic explanation readiness.
- Do not treat response-format review as provider-level response format enforcement or production benchmark completion.
- Do not treat `deepseek_production_activation_receipt` as provider benchmark success, provider response_format enforcement, bounded retry/repair readiness, token-cost production proof, `auto_after_task` production readiness, or production DeepSeek explanation completion.
- Do not treat `scripts/deepseek_governance_contract.py` passing as real provider benchmark success, provider response-format enforcement, bounded retry/repair readiness, auto-after-task production readiness, or production DeepSeek explanation completion.

### Recommended Commit Message

```text
Stabilize DeepSeek pro explanation benchmark
```

## LTG-08: ECharts 次日图谱成熟版

### Current Status

- ECharts initial and maturing chart contracts exist.
- Current display includes latest close, reference lines, operation zones, data credibility, and DeepSeek status.
- The cache payload now exposes `interaction_readiness_audit` and `interaction_readiness_rows` so hover/click evidence, reference-line source display, operation-zone guardrails, position-conflict visibility, DeepSeek status visibility, read-only frontend boundaries, and Streamlit parity gaps are auditable.
- The cache payload now exposes `next_session_replacement_activation_receipt` and `next_session_replacement_activation_rows`: this local receipt converts exact ECharts payload readiness, interaction readiness, reference/zone/context visibility, frontend read-only boundaries, Streamlit parity review, browser visual QA, performance trace, durable evidence, and production replacement blockers into one next-step checklist. It keeps `production_replacement_complete=false`, `streamlit_parity_complete=false`, `browser_visual_qa_done=false`, `browser_performance_trace_done=false`, and `durable_ci_evidence_complete=false`.
- The cache payload now exposes `next_session_browser_qa_runbook_contract`, `next_session_browser_qa_evidence_summary`, `next_session_browser_qa_review_contract`, and their rows. These fields pin the `#next` route, desktop/laptop/tablet/mobile viewport matrix, ignored `.stock_ming_3/motion_qa` artifact policy, default-motion and reduced-motion coverage, local evidence gaps, and explicit review state without opening a browser or submitting screenshots.
- `POST /api/next-session/browser-qa-review` is a button-gated local artifact review. It only reads ignored local runner reports for `#next`, records `next_session_browser_qa_review_contract`, and keeps `streamlit_parity_complete=false` and `production_replacement_complete=false`.
- `scripts/next_session_map_contract.py` is now part of the local push gate. It validates the exact ECharts payload, interaction readiness, reference/zone/position/DeepSeek visibility, GET cache envelope, button-gated local task, `#next` browser QA runbook/evidence/review boundaries, and React API-client/read-only boundaries while keeping `streamlit_parity_complete=false`, `production_replacement_complete=false`, `browser_visual_qa_done=false`, and `browser_performance_trace_done=false`.

### Gaps

- Interaction can still be improved after the current readiness audit.
- Evidence hover/click contracts are visible, but legacy parity review remains pending.
- Operation zone details are visible through guardrail rows, but full legacy interaction comparison is incomplete.
- Position conflict visualization is present, but clarity can still be improved.
- Full parity with legacy Streamlit chart is incomplete.
- The replacement activation receipt and `#next` browser QA contracts are next-step checklists/local artifact summaries only; they do not run browser QA, complete Streamlit parity, create durable CI/release evidence, or promote production replacement.
- The Next-session map push-gate contract is local only; browser visual QA, performance trace, Streamlit parity, and production replacement remain pending.

### Implementation Phases

1. Finish hover/click evidence drilldown.
2. Add clearer operation zone and reference line source display.
3. Improve empty/cache-missing states.
4. Compare against legacy Streamlit visual expectations.

### Acceptance Criteria

- Missing cache state is clear.
- Available cache renders a complete chart.
- `interaction_readiness_audit` distinguishes ready contracts, blockers, and parity-pending items.
- `scripts/next_session_map_contract.py` passes while reporting `streamlit_parity_complete=false`, `production_replacement_complete=false`, `browser_visual_qa_done=false`, and `browser_performance_trace_done=false`.
- `next_session_replacement_activation_receipt.local_activation_receipt_ready=true` only means the local payload/interaction/read-only prerequisites are clear enough for explicit Streamlit parity, browser visual QA, performance trace, and durable evidence review. It is not browser QA, performance trace, Streamlit parity, durable evidence, or production replacement completion.
- `next_session_browser_qa_runbook_contract.local_runbook_ready=true` only means the `#next` route, viewport matrix, and artifact policy are fixed.
- `next_session_browser_qa_evidence_summary.local_browser_qa_evidence_found=true` only means ignored local runner reports were summarized; even passing local evidence is not CI/release evidence.
- `next_session_browser_qa_review_contract.local_browser_qa_review_ready=true` is allowed only after explicit POST review and complete local default/reduced-motion evidence, and still keeps `streamlit_parity_complete=false` and `production_replacement_complete=false`.
- Frontend does not compute action.
- Frontend does not mutate price, position, or `operation_zones`.
- `production_replacement_complete` remains false until legacy parity is actually complete.

### Forbidden

- Do not calculate trade action in React.
- Do not rewrite backend packet values in the chart layer.
- Do not hide freshness or credibility warnings.
- Do not treat `scripts/next_session_map_contract.py` passing as browser visual QA, performance trace, Streamlit parity, or production ECharts replacement completion.
- Do not treat `next_session_replacement_activation_receipt` as browser visual QA, performance trace, Streamlit parity, durable evidence, or production ECharts replacement completion.
- Do not treat `next_session_browser_qa_evidence_summary` or `next_session_browser_qa_review_contract` as CI evidence, Streamlit parity, durable release evidence, or production ECharts replacement.

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
- On 2026-06-14, `npm run tauri build` completed locally and produced an executable macOS Mach-O release binary at `desktop/src-tauri/target/release/stock_ming_command_center`. Desktop preflight now records binary size, modified time, executable status, binary kind, `.app` bundle count, and DMG count without running npm, cargo, Tauri, FastAPI, providers, models, config reads, log writes, or trades.
- React API client now returns a safe `backend_offline_or_unreachable` envelope when local FastAPI is unavailable, and `BackendOfflineNotice` surfaces a clear offline state with display-safe API base text, without calling providers, models, GitHub, or trades.
- Desktop preflight now exposes `backend_offline_ux_contract` and `backend_offline_ux_rows` as a static frontend source audit; packaged runtime offline UX validation remains pending.
- Desktop preflight now exposes `packaged_runtime_qa_contract` and `packaged_runtime_qa_rows`, a static package QA matrix for release artifact QA, backend startup strategy, packaged offline UX, config/log runtime paths, signing/notarization, startup external-call boundary, and secret bundle boundary.
- `packaged_runtime_qa_contract.release_binary_qa_passed=true` can now be set when the local release binary exists, is non-empty, is executable, and was not produced by GET cache. This only closes the local binary artifact QA row; it keeps packaged runtime QA, `.app`/DMG detection, backend startup, offline UX, config/log runtime behavior, signing, notarization, and production package completion pending.
- Desktop preflight now exposes `tauri_release_manifest_contract` and `tauri_release_manifest_rows`, a local release-manifest contract covering app identity (`productName` / version / bundle identifier), `frontendDist`, local dev URL, icon asset, ignored generated artifacts, backend startup policy, config/log path policy, packaged QA gaps, signing/notarization gaps, and startup no-external/no-trade boundaries. It keeps `local_release_manifest_ready=true` while `ready_for_production_package_promotion=false` and `production_package_complete=false`.
- Desktop preflight now exposes `production_package_readiness_receipt`: a local next-step receipt that ties production readiness, runtime contract, artifact detection, backend-offline UX source contract, blocker audit, and packaged QA matrix into one LTG-09 checkpoint. It can mark `ready_for_explicit_tauri_build=true`, but keeps `production_package_complete=false`, `tauri_build_executed_by_receipt=false`, `npm_or_cargo_executed_by_receipt=false`, `tauri_runtime_started_by_receipt=false`, `packaged_app_opened_by_receipt=false`, `fastapi_started_by_receipt=false`, `config_values_read_by_receipt=false`, and `log_files_written_by_receipt=false`.
- `scripts/tauri_desktop_contract.py` is now part of the local push gate. It validates desktop preflight cache, production runtime contract, backend-offline UX source contract, packaged runtime QA matrix, release manifest contract, production blocker audit, production package readiness receipt, frontend secret boundary, and no-build/no-runtime/no-config/no-log/no-provider/no-trade boundaries while `production_package_complete=false`.
- Production package is incomplete.

### Gaps

- Rust/Cargo production environment.
- `npm run tauri build` can produce a local release binary, and local binary artifact QA can pass, but repeatable `.app`/DMG package acceptance and runtime QA are not yet complete.
- Packaged FastAPI sidecar or manual backend launch strategy validation.
- Local config path is declared as policy, but not validated in packaged runtime.
- Log path is declared as policy, but not validated in packaged runtime.
- macOS package flow.
- Friendly failure prompts exist at source-contract level; they still need packaged Tauri runtime validation.
- `packaged_runtime_qa_contract.status=packaged_runtime_qa_contract_ready_validation_pending` means the QA matrix is repeatable and visible, not that the packaged app has been opened or validated.
- `tauri_release_manifest_contract.status=release_manifest_contract_ready_packaged_execution_pending` means the release identity/dist/path/safety manifest is locally ready, not that Tauri build, packaged app launch, runtime QA, signing, notarization, or production promotion is complete.
- `production_runtime_contract.status=runtime_contract_ready_packaged_validation_pending` means the path/startup contract is declared only; it is not packaged runtime proof.
- `tauri_build_artifact.status=artifact_detected` means a local release binary exists; it is not sidecar/offline UX/signing/notarization proof and the artifact remains ignored by git.
- `tauri_build_artifact.packaged_app_bundle_detected=false` and `distribution_dmg_detected=false` are expected until a future explicit package/bundle flow creates and validates those artifacts.
- `packaged_runtime_qa_contract.release_binary_qa_passed=true` is only local binary artifact evidence; it is not packaged app launch, backend startup validation, offline UX validation, config/log runtime validation, signing, notarization, or production package promotion.
- `backend_offline_ux_contract.status=frontend_offline_notice_ready_packaged_runtime_validation_pending` means the React source path is ready, but the packaged app has not been opened and validated offline.
- `production_blocker_audit.status=production_package_blocked` is expected until build artifact QA, backend startup strategy, packaged offline UX, config/log runtime behavior, and macOS signing/notarization are validated.
- `production_package_readiness_receipt.status=tauri_package_readiness_receipt_ready_build_pending` or `tauri_package_readiness_receipt_ready_packaged_qa_pending` only clarifies the next safe explicit step. It does not run `npm`, `cargo`, Tauri, packaged app, FastAPI, config reads, log writes, provider/model calls, or production package promotion.
- `scripts/tauri_desktop_contract.py` is a local regression guard only; it does not run Tauri dev/build, open a packaged app, prove signing/notarization, read config values, write logs, or complete production desktop acceptance.

### Implementation Phases

1. Stabilize `tauri dev` on supported local machines.
2. Define and validate FastAPI startup strategy: sidecar or explicit manual process.
3. Add production package build and artifact checks.
4. Keep `tauri_release_manifest_contract` current as app identity, dist, artifact-ignore, backend-startup, config/log, QA-gap, and signing-gap requirements change.
5. Keep `production_package_readiness_receipt` current so the next explicit build/package-QA step is visible without converting preflight into production completion evidence.
6. Validate config/log location behavior in packaged runtime without exposing secrets.
7. Validate packaged-runtime backend-offline UI and macOS signing/notarization flow.

### Acceptance Criteria

- `tauri dev` passes.
- `tauri build` passes.
- `tauri_build_artifact` detects the local release binary without GET cache executing `npm`, `cargo`, or Tauri.
- `tauri_build_artifact.binary_executable=true`, `binary_kind=macos_mach_o_release_binary`, and `packaged_runtime_qa_contract.release_binary_qa_passed=true` are visible after an explicit successful local build.
- `.app` bundle and DMG detection remain separate from release binary QA; missing `.app`/DMG keeps packaged runtime QA pending.
- Backend-offline UI is friendly at React source-contract level and packaged runtime validation is separately tracked.
- Packaged runtime QA matrix is visible, keeps artifact/backend/offline/config-log/signing checks pending, and preserves startup no-external/no-trade boundaries.
- Local config and token/key are not exposed to frontend.
- Release manifest rows are visible in UI and local push gate, showing app identity, `frontendDist`, local dev URL, icon asset, generated artifact ignore policy, backend startup policy, config/log policy, packaged runtime QA gap, signing/notarization gap, `tauri_build_executed=false`, `packaged_app_opened=false`, `fastapi_started=false`, `config_values_read=false`, and `log_files_written=false`.
- `production_runtime_contract` declares config/log paths, startup strategy, and frontend secret boundary without reading config values, writing log files, starting FastAPI, or calling providers/models.
- `production_blocker_audit.package_ready=true` only after repeatable build artifact QA is verified, backend startup strategy is settled, config/log paths are validated in packaged runtime, packaged-runtime offline UX is validated, and signing/notarization is addressed.
- Production package readiness receipt rows are visible in UI, `allowed_next_step=explicit_tauri_build_then_packaged_runtime_qa_review`, and `not_allowed_next_steps` explicitly blocks GET cache npm/cargo/Tauri build, packaged app launch, FastAPI autostart, release-artifact detection as runtime QA, and preflight receipt as production package completion.
- `scripts/tauri_desktop_contract.py` passes in the local push gate while reporting `tauri_build_executed=false`, `packaged_runtime_qa_done=false`, `production_package_complete=false`, `does_not_run_tauri=true`, `does_not_run_npm=true`, `does_not_run_cargo=true`, and `production_package_readiness_receipt_ready=true`.

### Forbidden

- Do not bundle secrets into frontend or app package.
- Do not claim production desktop completion from preflight only.
- Do not claim `production_runtime_contract` as packaged runtime validation; it is a path/startup policy contract.
- Do not claim a detected release binary as production package completion.
- Do not claim `backend_offline_ux_contract` as packaged runtime offline validation.
- Do not claim `packaged_runtime_qa_contract` as packaged runtime validation; it is a static QA matrix.
- Do not claim `tauri_release_manifest_contract` as Tauri build execution, packaged app launch, runtime QA, signing/notarization, or production package completion.
- Do not claim `production_blocker_audit` as production package completion while status remains `production_package_blocked`.
- Do not claim `production_package_readiness_receipt` as build execution, packaged app launch, FastAPI startup, config/log runtime validation, signing/notarization, packaged runtime QA, or production package completion.
- Do not claim `scripts/tauri_desktop_contract.py` passing as Tauri build execution, packaged runtime QA, signing/notarization, or production package completion.
- Do not auto-call providers/models during `cache_only` app startup or initial render; future desktop `live_light` must still use the same opt-in POST bootstrap task, mode display, and rate-limit boundary as the web client.

### Recommended Commit Message

```text
Package Command Center 3 Tauri desktop shell
```

## LTG-10: Streamlit 完全退出普通主流程

### Current Status

- Streamlit is marked `legacy/admin/debug`.
- Legacy cache now exposes `primary_workflow_exit_audit`, `primary_workflow_exit_rows`, and `primary_workflow_route_rows`, making the ordinary-workflow exit status visible without opening Streamlit or running legacy tools.
- Legacy cache now exposes `streamlit_fallback_dependency_contract` and `streamlit_fallback_dependency_rows`, separating Command Center 3 primary-ready routes, ordinary-flow partial fallback dependencies, and retained legacy/admin/debug dependencies. This is a local dependency contract only; it does not remove Streamlit fallback, open Streamlit, run legacy tools, create tasks, or call providers/models/GitHub.
- Legacy cache now exposes `streamlit_retirement_readiness_receipt` and rows: a local LTG-10 next-step receipt that summarizes primary-exit blockers, fallback dependencies, ordinary blocking workflows, admin/debug retained blockers, no-feature-cut requirements, and the only allowed next step: explicit replacement parity review followed by Streamlit fallback retirement review. It keeps `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, and `streamlit_fallback_retained=true`.
- `scripts/streamlit_legacy_contract.py` is now part of the local push gate. It validates legacy cache read-only policy, `legacy/admin/debug` marking, React/Tauri primary-entry policy, ordinary-workflow exit blockers, fallback dependency contract, no-feature-cut requirements, no Streamlit execution, no legacy tool execution, no task creation, no provider/model/GitHub calls, no trade, and no action mutation while `ordinary_workflow_exit_complete=false`.
- It has not fully exited ordinary usage paths.

### Gaps

- React/Tauri does not yet cover every ordinary operation.
- Some old tools still need Streamlit fallback.
- `primary_workflow_exit_audit.status=ordinary_workflow_exit_partial_fallback_required` is expected until all ordinary workflows are proven in Command Center 3 and fallback removal is safe.
- `streamlit_retirement_readiness_receipt.status=streamlit_retirement_receipt_ready_fallback_blocked` is expected while Candidate Radar parity, full-pool/deep-scan acceptance, provider-backed parity, browser/performance QA, and admin/debug replacement or retirement decisions remain incomplete.
- `scripts/streamlit_legacy_contract.py` is a local regression guard only; it does not remove Streamlit fallback, prove replacement parity, run old tools, open Streamlit, or complete ordinary-workflow exit.

### Implementation Phases

1. Identify ordinary user workflows still depending on Streamlit.
2. Migrate those workflows to React/Tauri + FastAPI.
3. Keep `streamlit_fallback_dependency_contract` current so every fallback dependency has a removal criterion and no feature-cut boundary.
4. Keep `streamlit_retirement_readiness_receipt` current so the next explicit parity/retirement review is visible without deleting fallback or marking completion.
5. Keep Streamlit for debug/admin/fallback only.
6. Preserve old-module guards.
7. Promote `primary_workflow_exit_audit` to complete only after route coverage has no fallback blockers and legacy removal is safe.

### Acceptance Criteria

- Ordinary users can use Command Center 3 desktop as the main surface.
- Streamlit does not auto-create tasks.
- Streamlit does not bypass guards.
- Legacy strong-action protection remains.
- `primary_workflow_exit_audit.ordinary_workflow_exit_complete=true` only when route coverage has no remaining Streamlit fallback dependencies and the migration checklist is clear.
- `streamlit_fallback_dependency_contract.full_streamlit_removal_ready=true` only when ordinary fallback dependencies and retained admin/debug fallback dependencies are all cleared with replacement parity proven.
- Streamlit retirement readiness receipt rows are visible in UI, `allowed_next_step=explicit_replacement_parity_review_then_streamlit_fallback_retirement_review`, and `not_allowed_next_steps` explicitly blocks GET cache opening Streamlit, running legacy tools, creating tasks, page render retiring fallback, deleting `app.py`, or treating the receipt as retirement completion.
- `scripts/streamlit_legacy_contract.py` passes in the local push gate while reporting `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, `streamlit_retirement_readiness_receipt_ready=true`, and `does_not_open_streamlit=true`.

### Forbidden

- Do not delete Streamlit fallback before replacement workflows are usable.
- Do not let legacy pages bypass freshness, model, or action guardrails.
- Do not present Streamlit as the primary 3.0 surface.
- Do not treat local exit audit as complete while status remains `ordinary_workflow_exit_partial_fallback_required`.
- Do not treat `streamlit_retirement_readiness_receipt` as fallback removal, `app.py` deletion, replacement parity, admin/debug retirement, or complete Streamlit exit.
- Do not treat `scripts/streamlit_legacy_contract.py` passing as Streamlit fallback removal, replacement parity, admin/debug retirement, or complete ordinary-workflow exit.

### Recommended Commit Message

```text
Retire Streamlit from primary user workflow
```

## LTG-11: 测试 / CI / Smoke / 安全扫描标准化

### Current Status

- Local test, frontend build, smoke, and diff checks are available.
- `scripts/push_gate_3_0.sh` now codifies the local push gate: Python tests, desktop build, smoke, diff check, high-risk secret scan, generated artifact scan, and final clean-worktree check.
- `scripts/data_health_freshness_contract.py` is now part of the local push gate. It validates LTG-01 Data Health contracts and the freshness production blocker audit remain cache-only, provider-backed acceptance stays pending, and score/support/preview/action boundaries are not silently weakened.
- `scripts/tushare_acceptance_contract.py` is now part of the local push gate. It validates LTG-02 Tushare matrix/readiness/contracts and provider evidence gap ledger remain button-gated, local, no-provider, no-trade, and no-action, while provider-backed full-interface acceptance remains pending.
- `scripts/factor_test_lab_contract.py` is now part of the local push gate. It validates LTG-03 Factor Test Lab research metrics, small-pool readiness, storage query consumption, production QA, and provider validation blocker audit stay local/research-only while provider-backed small-pool and full-market validation remain pending.
- `scripts/factor_universe_contract.py` is now part of the local push gate. It validates LTG-04 universe modes, local read-plan storage-query consumption, button-gated task catalog, React read-only display, partial-pool-not-full-market-proof visibility, no-provider/no-model/no-trade/no-action boundaries, and keeps worker batch execution, rank/zscore, neutralization, full-pool validation, and production universe research pending.
- `scripts/deepseek_governance_contract.py` is now part of the local push gate. It validates LTG-07 manual/default-off governance, sanitizer whitelist, parse-failed discard, JSON stability blockers, response-format review blockers, button gating, model strategy, no-model-call, no-secret, no-trade, and no-action boundaries while provider-backed benchmark and production automatic explanation remain pending.
- `scripts/next_session_map_contract.py` is now part of the local push gate. It validates LTG-08 exact ECharts payload, interaction readiness, reference/zone/position/DeepSeek visibility, current GET cache envelope, button-gated local task, React API-client/read-only display, no-browser, no-provider, no-trade, and no-action boundaries while browser visual QA, performance trace, Streamlit parity, and production replacement remain pending.
- `scripts/candidate_radar_contract.py` is now part of the local push gate. It validates LTG-13 Candidate Radar cache reads, local quick-scan task gating, full-pool/deep-scan plan-only boundaries, no-feature-loss QA, replacement-gap triage, promotion-blocker audit, result-delta clarity, and no-trade/no-action boundaries while production radar replacement remains pending.
- `scripts/storage_contract.py` is now part of the local push gate. It validates LTG-05 Storage cache, schema/version preflights, dry-run packets, DuckDB query policy, artifact cleanup review, and storage task catalog gating remain local/no-write/no-provider/no-trade while physical storage production remains pending.
- `scripts/worker_contract.py` is now part of the local push gate. It validates LTG-06 Worker cache, dispatch plans, production blocker audit, healthcheck QA, activation review, scheduler default-off, no-external-call, no-provider-call, no-trade, and no-action boundaries while production worker activation remains pending.
- `scripts/tauri_desktop_contract.py` is now part of the local push gate. It validates LTG-09 desktop preflight cache, runtime contract, backend-offline UX source contract, packaged runtime QA matrix, production blocker audit, no-build/no-runtime/no-config/no-log/no-provider/no-trade boundaries, and keeps production desktop package completion pending.
- `scripts/streamlit_legacy_contract.py` is now part of the local push gate. It validates LTG-10 Legacy cache, ordinary-workflow exit audit, fallback dependency contract, React Legacy page boundaries, no-feature-cut requirements, no Streamlit execution, no legacy tool execution, no task creation, no-provider/no-model/no-GitHub/no-trade/no-action boundaries, and keeps Streamlit full retirement pending.
- `scripts/trade_isolation_contract.py` is now part of the local push gate. It validates LTG-12 risk cache trade-isolation audit, task catalog no-order/no-trade route boundaries, frontend no-trade/no-action visibility, no broker/order execution path, and future real-trading separation while real trading remains disconnected.
- `scripts/push_gate_3_0.sh` can optionally write a local Markdown release-readiness report when `PUSH_GATE_REPORT_PATH` is set; report generation runs before the final clean-worktree check so unignored in-repo reports still block push.
- Secret/artifact keyword hits are separated into high-risk failures versus review output so sanitizer/test/docs mentions can be explained instead of silently ignored.
- `scripts/secret_keyword_review_contract.py` now gives the ordinary keyword scan a structured local contract: it classifies tracked keyword hits by category and top files, emits counts only, suppresses raw source lines, and fails if high-risk tracked secret-looking values appear outside tests/docs. It does not call external services or prove periodic human allowlist review is complete.
- `GET /api/audit/cache` now exposes `release_gate_readiness_audit`, `release_gate_readiness_rows`, and local workflow inventory. This is a static local contract check for `scripts/push_gate_3_0.sh`, not a CI status check and not production completion proof.
- `GET /api/audit/cache` now exposes `release_gate_push_readiness_receipt` and `release_gate_push_readiness_rows`: a local-only receipt that selects the safe sequence `run_scripts_push_gate_3_0_then_git_push_then_inspect_remote_actions_if_needed`. It keeps fresh local gate output, matching remote Actions status, latest green run evidence, and periodic allowlist review as separate evidence items.
- `GET /api/audit/cache` now also exposes `ci_notification_triage_contract` and `ci_notification_triage_rows`: a local-only triage contract for GitHub Actions failure emails. It separates local push-gate readiness, static CI mirror presence, stale-email risk, and the remote failed step/log evidence still required from the Actions run page. It does not call GitHub API, fetch workflow logs, or prove the remote run is green.
- `.github/workflows/command-center-3-push-gate.yml` now mirrors the local push gate by creating `.venv`, installing desktop dependencies, and running `scripts/push_gate_3_0.sh` with `PYTHON_BIN=.venv/bin/python`.

### Gaps

- CI mirror workflow exists, but remote CI status is still not local proof until a pushed run is inspected; current audit only proves static workflow presence.
- Push readiness receipt is local and static: `local_receipt_ready=true` means the explicit gate/push/remote-review path is well defined, not that the gate has just run or that the latest remote run is green.
- CI failure email triage is visible, but it only tells the user which remote evidence is required: matching commit/head, failed step name, and safe log excerpt. It cannot dismiss a failure email or mark CI green without that remote run evidence.
- Push gate still needs periodic review of false-positive allowlists; current audit keeps `false_positive_allowlist_review_pending` visible.
- Structured keyword review is present, but it is still a local classification contract; periodic human allowlist review and remote CI evidence remain separate.
- Tushare acceptance contract is present, but it is still a local matrix/readiness/evidence-gap guard; real provider-backed interface samples remain a later LTG-02 acceptance phase.
- Factor Test Lab contract is present, but it is still a local research-boundary guard; provider validation blocker audit only centralizes remaining blockers, while real small-pool and full-market research validation remain a later LTG-03 acceptance phase.
- Factor universe contract is present, but it is still a local read-plan/read-only guard; worker-backed batch execution, rank/zscore, neutralization, provider-backed validation, factor combination research, and full-pool production research remain later LTG-04 acceptance phases.
- DeepSeek governance contract is present, but it is still a local sanitizer/response-format/no-model-call guard; real provider-backed benchmark, provider response-format enforcement, bounded retry/repair execution, and production auto-after-task readiness remain later LTG-07 acceptance phases.
- Next-session map contract is present, but it is still a local no-browser/no-provider guard; browser visual QA, performance trace, Streamlit parity, and production ECharts replacement remain later LTG-08 acceptance phases.
- Candidate Radar contract is present, but it is still a local replacement-boundary guard; the promotion-blocker audit only centralizes remaining blockers, while real full-pool/deep-scan execution, provider-backed parity acceptance, browser performance trace, and visual QA remain later LTG-13 acceptance phases.
- Storage contract is present, but it is still a local preflight/dry-run guard; real physical schema validation, migration, manifest validation, partition migration, compaction, TTL refresh execution, and cleanup delete execution remain later LTG-05 acceptance phases.
- Worker contract is present, but it is still a local no-process-start guard; real Celery/Redis startup, Redis broker health, synthetic healthcheck execution, cross-process controls, task log persistence, and scheduler production config remain later LTG-06 acceptance phases.
- Tauri desktop contract is present, but it is still a local preflight/runtime/package-QA boundary guard; real `tauri dev`, repeatable `tauri build`, packaged runtime launch QA, config/log runtime validation, backend startup strategy acceptance, and macOS signing/notarization remain later LTG-09 acceptance phases.
- Streamlit legacy contract is present, but it is still a local no-Streamlit-execution guard; real ordinary-flow parity, fallback removal, admin/debug retirement, and complete Streamlit exit remain later LTG-10 acceptance phases.
- Trade isolation contract is present, but it is still a local no-broker/no-order guard; it proves current Command Center 3 research/cache/task/frontend boundaries, not a future real-trading integration design or broker acceptance.
- Optional local reports are evidence for one gate run, not durable CI status and not production completion proof.

### Implementation Phases

1. Document the release gate in one place.
2. Keep `unittest`, frontend build, smoke, and `git diff --check` mandatory.
3. Add repeatable secret and generated-artifact scan commands.
4. Keep ordinary keyword review structured and count-only so logs do not expose raw matched source lines.
5. Keep optional local release-readiness reports explicit and outside tracked artifacts unless intentionally reviewed.
6. Add local LTG contracts as each migration surface becomes risky enough to need regression guards.
7. Add CI coverage where safe and affordable.

### Acceptance Criteria

- Python tests pass.
- Frontend build passes.
- `scripts/smoke_3_0.sh` passes.
- `git diff --check` passes.
- Secret scan and generated artifact scan are clean or explained.
- Ordinary keyword review contract runs after high-risk scan, emits no raw matched source lines, and keeps periodic allowlist review visible as pending.
- Worktree is clean before push.
- Optional local release report records passed checks, branch/head, ahead count, and safety boundaries without pushing or calling providers.
- Data Health freshness contract keeps `freshness_production_blocker_audit` visible, local, no-provider, no-trade, and no-action while `production_freshness_gate_complete=false`.
- Tushare acceptance contract runs after Data Health and before static UI QA, and keeps `provider_backed_acceptance_done=false` / `production_tushare_pipeline_complete=false` visible.
- Factor Test Lab contract runs after Tushare acceptance and before static UI QA, and keeps `provider_backed_small_pool_validation_done=false` / `production_factor_test_validation_complete=false` visible.
- Factor universe contract runs after Factor Test Lab and before DeepSeek governance, and keeps `large_universe_pipeline_done=false`, `full_pool_validation_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, and `production_factor_universe_complete=false` visible.
- DeepSeek governance contract runs after Factor universe and before Next-session map, and keeps `provider_benchmark_done=false`, `response_format_enforced=false`, `retry_repair_policy_ready=false`, `auto_after_task_production_ready=false`, and `production_deepseek_explanation_complete=false` visible.
- Next-session map contract runs after DeepSeek governance and before Candidate Radar, and keeps `streamlit_parity_complete=false`, `production_replacement_complete=false`, `browser_visual_qa_done=false`, and `browser_performance_trace_done=false` visible.
- Candidate Radar contract runs after Next-session map and before static motion QA, and keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, and `deep_scan_done=false` visible.
- Storage contract runs after Candidate Radar and before static motion QA, and keeps `production_storage_complete=false`, `schema_migration_executed=false`, `partition_migration_executed=false`, `physical_compaction_executed=false`, and `cache_ttl_refresh_executed=false` visible.
- Worker contract runs after Storage and before static motion QA, and keeps `production_worker_complete=false`, `healthcheck_executed=false`, `activation_ready=false`, `worker_started=false`, `redis_pinged=false`, and `scheduler_started=false` visible.
- Tauri desktop contract runs after Worker and before static motion QA, and keeps `tauri_build_executed=false`, `packaged_runtime_qa_done=false`, `production_package_complete=false`, `does_not_run_tauri=true`, `does_not_run_npm=true`, and `does_not_run_cargo=true` visible.
- Streamlit legacy contract runs after Tauri desktop and before static motion QA, and keeps `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, and `does_not_open_streamlit=true` visible.
- Trade isolation contract runs after Streamlit legacy and before static motion QA, and keeps `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, and `future_real_trading_requires_separate_project=true` visible.
- `release_gate_readiness_audit.local_gate_ready=true` and `ci_mirror_ready=true` are visible in the audit cache, while `release_gate_complete` remains false until allowlist review and actual remote check evidence are proven.
- `ci_notification_triage_contract.status=ci_notification_triage_ready_remote_logs_required` is visible in the audit cache, while `remote_actions_status_known=false`, `remote_failure_logs_available=false`, `latest_remote_run_verified_green=false`, and `can_dismiss_failure_email_without_matching_head_and_logs=false` remain explicit until the failed Actions run is inspected.

### Forbidden

- Do not bypass failing tests.
- Do not use `git add .`.
- Do not push without user confirmation.
- Do not treat a local push-gate pass, static CI mirror, old email notification, or CI triage contract as proof that the latest remote Actions run passed.
- Do not fetch GitHub Actions logs from cache APIs or page render.

### Recommended Commit Message

```text
Add release gate readiness audit
```

## LTG-12: 真实交易链路继续保持隔离

### Current Status

- Automatic real trading is not connected.
- Multiple packets and APIs declare `does_not_execute_trades` and `does_not_modify_strategy_action`.
- `GET /api/risk/cache` now exposes `trade_isolation_audit`, `trade_isolation_rows`, and `trade_isolation_boundary_rows`: a cache-only audit of risk policy, task catalog POST route boundaries, and frontend no-trade/no-action visibility.
- `GET /api/risk/cache` now exposes `trade_isolation_release_receipt` and rows: a local LTG-12 release receipt that allows research-client release only while keeping `ready_for_real_trading_integration=false`, `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, and `future_real_trading_requires_separate_project=true`.
- `scripts/trade_isolation_contract.py` is now part of the local push gate. It reads only local risk cache, task catalog, frontend source contracts, and the push-gate script, then keeps `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, and `trade_execution_api_enabled=false` auditable.

### Gaps

- Future productionization could accidentally blur research and execution boundaries.
- Any eventual trading integration would need a separate project, separate approvals, and separate safety design.
- The audit proves current Command Center 3 cache/task/frontend contracts, not a future broker/order integration design.
- The release receipt is not real-trading approval; it only records that the current research client remains isolated from broker/order execution.
- The push-gate contract is local and static; it blocks accidental boundary regression but does not prove broker integration safety, simulated trading, order routing, or production trade compliance.

### Implementation Phases

1. Keep all current 3.0 migration work research/client-side only.
2. Preserve action mutation guards in cache, task, frontend, model, factor, storage, and worker paths.
3. Add tests whenever a new route or task can affect decision-adjacent data.
4. Keep `trade_isolation_release_receipt` current so release candidates can state research-client safety without implying broker/order approval.
5. Keep the local trade-isolation push-gate contract updated whenever task routes, risk cache policy, packet registry boundaries, or frontend task controls change.

### Acceptance Criteria

- No automatic order path exists.
- Research/factor/model/cache/frontend paths cannot mutate `strategy action`.
- Any future trade integration is explicitly out of this roadmap unless a separate approved design exists.
- `trade_isolation_audit.status=trade_isolation_ready`, with zero blockers and all known POST routes covered by the task catalog.
- `trade_isolation_release_receipt.status=trade_isolation_release_receipt_ready_research_release_only`, with `allowed_next_step=continue_research_client_release_or_create_separate_real_trading_project_design` and not-allowed shortcuts blocking broker adapters, order endpoints, model/factor-to-order paths, frontend trade submission, and treating the receipt as real-trading approval.
- `scripts/trade_isolation_contract.py` passes in the local push gate while reporting `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, `does_not_modify_holdings=true`, `trade_isolation_release_receipt_ready=true`, and `future_real_trading_requires_separate_project=true`.

### Forbidden

- Do not connect broker/order APIs in ordinary migration work.
- Do not execute real trades.
- Do not let model or factor output become orders.
- Do not treat the local trade-isolation contract as approval to connect real broker/order execution; it only proves current isolation remains intact.
- Do not treat `trade_isolation_release_receipt` as approval to connect broker/order execution; it only proves the current research client stays isolated.

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
- A button-gated local `run_candidate_radar_full_pool_local_scan` task now consumes explicit local universe payload/cache rows and writes `full_pool_local_execution_receipt` / rows. This proves the React/FastAPI/task/storage path can execute a local full-pool-like universe without UI stalls or external calls, but keeps `production_full_pool_scan_done=false`, `provider_backed_acceptance_done=false`, `worker_backed_execution_done=false`, and `legacy_retirement_ready=false`.
- A button-gated local `run_candidate_radar_deep_scan_plan` task now writes `deep_scan_plan`, stage rows, parity rows, required signal rows, and blocker rows so fast-scan migration can audit no-feature-loss readiness without executing deep scan, refreshing providers, or calling DeepSeek.
- A button-gated local `run_candidate_radar_deep_scan_local_review` task now writes `deep_scan_local_review_receipt` and `deep_scan_local_review_rows`. It reviews local candidate evidence, trigger/invalidation presence, legacy parity blockers, provider gaps, freshness visibility, and trade/action isolation without refreshing providers, calling DeepSeek, running worker deep-scan execution, or marking `deep_scan_done=true`.
- Candidate radar packets now expose `fast_scan_readiness_audit` and `fast_scan_readiness_rows`, proving the local quick/watchlist/custom scan contract is cache/task based, page render does not scan, legacy/provider/freshness gaps are visible, and full-pool/deep-scan remain pending rather than silently downgraded.
- Candidate radar packets now expose `fast_scan_runtime_budget_contract` and `fast_scan_runtime_budget_rows`: local sync display is capped, local pool input normalization has a fixed budget, large universes must move to worker execution, and truncation is reported as a visible gap instead of being hidden.
- Candidate radar packets now expose `no_feature_loss_acceptance_contract` and `no_feature_loss_acceptance_rows`: this aggregates page-render/cache boundaries, local scan modes, legacy signal groups, legacy output fields, provider/freshness gaps, runtime budget, browser performance trace status, full-pool/deep-scan execution status, provider-backed acceptance, and trade/action isolation. It makes the local no-feature-loss QA surface visible but keeps `production_radar_replacement_complete=false`.
- Candidate radar packets now expose `replacement_gap_triage_contract` and `replacement_gap_triage_rows`: this locally classifies legacy-radar retirement gaps into critical, pending, blocking, and passed rows across legacy signal groups, output fields, provider coverage, freshness, previous-cache delta clarity, browser visual QA, performance trace, full/deep worker execution, provider-backed acceptance, and trade/action isolation. It keeps `legacy_retirement_ready=false` while any blocking gap remains.
- Candidate radar packets now expose `candidate_radar_promotion_blocker_audit` and `candidate_radar_promotion_blocker_rows`: this local cache-only audit centralizes why quick radar cannot yet be promoted to a production replacement. It keeps full-pool execution, deep-scan execution, provider-backed acceptance, browser QA evidence, browser performance trace, freshness, legacy retirement, no-trade, and no-action boundaries visible while `promotion_ready=false`, `production_radar_replacement_complete=false`, and `legacy_retirement_ready=false`.
- Candidate radar packets now expose `quick_scan_execution_receipt` and `quick_scan_execution_receipt_rows`: this local receipt summarizes the active cache/quick/watchlist/custom scan mode, task or cache call ledger, candidate input/display/truncation counts, local pool caps, legacy signal coverage, provider gaps, freshness boundary, result-delta visibility, full/deep/provider production blockers, and trade/action isolation. It is a user-facing execution receipt, not production replacement evidence.
- Candidate radar packets now expose `candidate_radar_production_activation_receipt` and `candidate_radar_production_activation_rows`: this local activation receipt converts the existing quick-scan receipt, no-feature-loss QA, promotion blockers, full-pool/deep-scan plans, provider-backed parity gap, browser visual/performance gap, legacy-retirement gate, and trade/action isolation into a single next-step checklist. It keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, and `durable_ci_evidence_complete=false`.
- Candidate radar packets now expose `legacy_parity_acceptance_receipt` and `legacy_parity_acceptance_rows`: this local receipt turns the old next-ticket radar's Top / Watch / Excluded split, evidence links, scoring dimensions, trigger / invalidation logic, holding comparison, candidate pool sources, scan filters, timeout fallback, manual deep research path, and output fields into explicit replacement gates. It is a no-feature-loss acceptance guard, not production replacement evidence; it keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `legacy_fallback_required=true`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `browser_visual_delta_qa_done=false`, and `browser_performance_trace_done=false`.
- Candidate radar packets now expose `result_delta_clarity_contract`, `result_delta_clarity_rows`, and `previous_cache_diff_rows`: candidate counts, display truncation, skipped reasons, provider gaps, freshness state, scan mode transitions, local-pool skips, and full/deep boundaries are visible without rescoring, refreshing providers, timers, browser QA, or trade/action mutation. When a previous SQLite radar packet exists, local scan tasks compute added/removed/rank/score/status deltas; when no previous packet exists, the missing baseline remains explicit.
- Candidate radar packets now expose `candidate_priority_explanation_contract` and rows: existing cache rank, existing score, action label, evidence summary, trigger/invalidation presence, and data gaps are explained per visible candidate without rescoring, reordering, refreshing providers, calculating action, or creating a trade signal.
- Candidate radar packets now expose `candidate_browser_qa_runbook_contract`, rows, and matrix rows. The runbook pins `#candidates`, desktop/laptop/tablet/mobile viewports, result-cluster readability, local-scan button visibility, result-delta gap visibility, mobile clipping checks, reduced-motion expectations, and the shared local browser runner. It does not open a browser or prove visual/performance acceptance.
- Candidate radar packets now expose `candidate_browser_qa_evidence_summary` and `candidate_browser_qa_evidence_rows`. This route-level reader summarizes ignored local `scripts/motion_browser_qa_runner.mjs` reports for `#candidates` only, including visual/performance pass state, review rows, report path, and no-provider/no-trade flags. It does not open a browser, write artifacts, commit screenshots, prove provider-backed parity, or mark `production_radar_replacement_complete`.
- `POST /api/candidate-radar/browser-qa-review` now creates a button-gated local review task for the `#candidates` ignored runner evidence. It records `candidate_browser_qa_review_contract` and rows, requires an explicit POST before `explicit_review_task_done=true`, and still keeps full-pool/deep-scan/provider-backed acceptance, legacy retirement, and production radar replacement blocked.
- On 2026-06-14, the explicit local browser runner completed default-motion and reduced-motion passes for the full LTG-14 route matrix; the Candidate Radar evidence reader found `#candidates` rows across desktop/laptop/tablet/mobile, and the button-gated Candidate Radar browser QA review reached `candidate_browser_qa_review_ready_local_artifact` with zero blocking review rows in the same local app session. This is local workstation evidence only: it does not promote browser artifacts to CI evidence, does not prove provider-backed parity, and does not mark `production_radar_replacement_complete=true`.
- Candidate Radar browser QA evidence now requires stricter motion/viewport coverage: default-motion must pass desktop/laptop/tablet/mobile and reduced-motion must also pass desktop/laptop/tablet/mobile before `candidate_browser_qa_evidence_passed_local_artifact` or `candidate_browser_qa_review_ready_local_artifact` can be treated as locally ready. Missing default or reduced-motion viewports stay visible as review gaps instead of being silently accepted.
- `scripts/candidate_radar_contract.py` is now part of the local push gate. It reads only local cache/service contracts and keeps cache GET, quick-scan task gating, full-pool plan, full-pool local receipt, deep-scan plan, deep-scan local review receipt, no-feature-loss QA, replacement-gap triage, promotion-blocker audit, result-delta clarity, candidate-priority explanation, no-provider, no-model, no-trade, and no-action boundaries auditable while `production_radar_replacement_complete=false` and `legacy_retirement_ready=false`.
- `scripts/candidate_radar_browser_qa_runbook.py` is now part of the local push gate after the LTG-13 contract and before generic motion QA. It is a static execution runbook only; it keeps `visual_qa_complete=false`, `browser_performance_trace_done=false`, `production_radar_replacement_complete=false`, and `legacy_retirement_ready=false`.
- Current 3.0 radar path is still not a full replacement for the legacy radar workflow.
- Runtime mode policy turns search-driven radar/quant projection into future mode-gated work: `cache_only` shows existing radar cache only, `manual` uses explicit scan/plan/review buttons, and future `live_light` may create a one-shot background task for a searched symbol or watchlist subset without starting full-market/deep scans on render.

### Gaps

- Need actual full-pool scan execution beyond the current local quick/watchlist/custom scans and full-pool readiness plan.
- Need worker-backed async execution for slower scans beyond the local fallback path.
- Deeper local scan coverage accounting and scan acceptance rows now exist for universe size, provider-blocked groups, stale inputs, missing provider data, degraded modes, freshness, local pool, full-pool boundary, and trade isolation; they are still cache/local-only and do not prove full-pool or provider-backed scan acceptance.
- Need clear distinction between quick scan, deep-scan readiness plan, real deep scan, and research-only candidates.
- The deep-scan readiness plan is not deep scan execution and does not prove legacy radar replacement.
- The deep-scan local review receipt is local evidence review only; it does not call DeepSeek, refresh providers, run worker deep-scan execution, prove provider-backed parity, or allow legacy radar retirement.
- Durable browser performance promotion and packaged runtime UI responsiveness validation are still pending. Local ignored browser runner reports can now prove a workstation pass, but they are not durable CI or packaged-runtime evidence.
- The no-feature-loss acceptance contract is local QA; it does not prove browser performance, real full-pool/deep-scan execution, or provider-backed parity acceptance.
- The replacement gap triage contract is local blocker classification; it does not execute full-pool/deep-scan, provider-backed acceptance, browser visual QA, or performance traces.
- The Candidate Radar promotion-blocker audit is local blocker aggregation; it does not clear blockers, execute scans, call providers/models, promote ignored browser artifacts, retire the legacy radar, or prove production replacement.
- The quick-scan execution receipt is local visibility evidence; it does not clear production blockers, execute full-pool/deep-scan, refresh providers, run browser performance QA, retire legacy radar, or prove full replacement.
- The full-pool local execution receipt is local universe execution evidence; it does not prove provider-backed full-market acceptance, production worker execution, browser QA, Streamlit retirement, or trading readiness.
- The deep-scan local review receipt is local candidate-evidence review evidence; it does not prove model-backed deep research, provider-backed acceptance, production worker execution, browser QA, Streamlit retirement, or trading readiness.
- The Candidate Radar production activation receipt is a local next-step checklist; it does not execute worker scans, call providers/models, promote browser artifacts, create CI evidence, retire the legacy radar, or prove full replacement.
- The Candidate Radar legacy parity acceptance receipt is local no-feature-loss gating; it blocks treating `gap_reported` as feature parity, blocks retiring the Streamlit radar fallback before provider/worker/browser acceptance, and still does not execute scans, call providers/models, run browser QA, or prove production replacement.
- The result-delta clarity contract is local QA; previous-cache diff is only complete when a prior persisted radar packet exists, and it still does not prove browser visual QA or production radar replacement.
- The candidate-priority explanation contract is local QA; it explains current cache ordering and evidence gaps only. It does not sort, rescore, calculate action, refresh data, or prove provider-backed full-pool/deep-scan acceptance.
- The Candidate Radar browser QA runbook is ready, but it is still a static plan; it does not prove the browser pass ran, and ignored local screenshots/reports are not durable CI or production acceptance.
- The Candidate Radar browser QA evidence reader can make local ignored `#candidates` report evidence visible, but local reports are still workstation artifacts, not durable CI proof, not provider-backed acceptance, and not full radar replacement.
- The Candidate Radar browser QA review task is now button-gated and local-only, but it still reviews ignored local artifacts rather than running browser QA in CI or proving provider-backed parity.
- A single default-motion browser pass is no longer sufficient local evidence; reduced-motion and all four target viewports must also be present before the browser QA evidence/review status can become locally ready.
- The local Candidate Radar push-gate contract is not a production radar run; it only blocks regressions where local quick scans, plan-only rows, no-feature-loss QA, replacement triage, promotion-blocker audit, result-delta clarity, or candidate-priority explanation could be mistaken for full replacement.
- `fast_scan_local_ready_full_pool_pending` is not production replacement; it only proves local readiness and visible gaps.
- Need parity acceptance before removing any Streamlit fallback.
- Need a search-to-quant projection workflow that validates the symbol, refreshes allowed light data, writes call ledger/model ledger, updates factor and next-session cache, and renders chart/provenance without reducing legacy radar signal coverage.
- Need explicit intraday-provider strategy before adding any realtime market state: every non-Tushare source must have provider identity, call ledger, freshness, mode gating, and safe-error status.

### Implementation Phases

1. Inventory legacy radar inputs, scoring fields, filters, exclusions, and output packet shape.
2. Build a fast local scan task that reads existing cache/storage first and returns a task receipt immediately.
3. Add progressive scan modes: `quick_cache_scan`, `watchlist_scan`, `custom_pool_scan`, `full_pool_plan`, `deep_scan_plan`, and later real `full_pool_scan` / `deep_scan`.
4. Add coverage metrics so the UI shows what was scanned, skipped, stale, or blocked.
5. Preserve signal parity before removing any legacy fallback.
6. Move slow provider refreshes behind explicit POST tasks instead of radar page render.
7. Add future search-driven "生成 3.0 量化推演" / "一键生成量化投研图谱" task for a single symbol or bounded watchlist subset.
8. Allow `live_light` radar/quant bootstrap only after cache render, with symbol limit, rate limit, task dedupe, and visible skipped state.

### Acceptance Criteria

- Page render does not start full-market scanning.
- POST scan returns `task_id` quickly and writes a candidate radar packet when done.
- POST full-pool local scan can consume an explicit local universe/payload, write a packet, show duplicate/truncation/provider/freshness gaps, and keep production full-pool acceptance pending.
- React shows progress, last successful packet, coverage, skipped reasons, and freshness state.
- Existing legacy radar signal groups are mapped or explicitly marked as not yet migrated.
- Missing provider data, provider-blocked groups, stale inputs, and degraded modes are reported as coverage gaps, not silently dropped.
- Local quick scan enforces and displays sync runtime budgets, including candidate display caps and local pool input caps.
- Full-pool plan lists worker requirements, filters, required signal groups, and blockers without scanning or refreshing providers.
- Deep-scan plan lists no-feature-loss parity rows, required signal rows, freshness, worker blockers, and trade/model boundaries without executing deep scan or calling DeepSeek.
- Deep-scan local review can be run only through explicit POST, reviews existing local candidate rows and gaps, writes `deep_scan_local_review_receipt`, and must keep `deep_scan_done=false`, `deepseek_called=false`, `provider_backed_acceptance_done=false`, `legacy_retirement_ready=false`, and `candidate_is_not_buy_instruction=true`.
- `fast_scan_readiness_audit.local_fast_scan_ready=true` only when page-render, local task, legacy gap, provider gap, freshness, last-cache, full-pool, deep-scan and trade boundaries are all visible.
- `no_feature_loss_acceptance_contract.local_no_feature_loss_contract_ready=true` only means the local QA surface is visible; `production_radar_replacement_complete` remains false until browser performance, real full-pool/deep-scan execution, and provider-backed parity acceptance are complete.
- `replacement_gap_triage_contract.local_triage_ready=true` only means blockers to retiring the legacy radar are classified and visible; `legacy_retirement_ready` must remain false while critical/provider/freshness/browser/performance/full-pool/deep-scan/provider-backed gaps remain.
- `quick_scan_execution_receipt.local_quick_scan_receipt_ready=true` only means the local cache/quick/watchlist/custom execution receipt and its gaps are visible. It must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false` until direct production evidence exists.
- `candidate_radar_production_activation_receipt.local_activation_receipt_ready=true` only means the next safe acceptance path is clear: explicit worker full-pool/deep-scan execution, provider-backed parity, browser visual/performance review, durable evidence, and legacy-retirement review. It must keep production completion flags false until those direct evidence items exist.
- `full_pool_local_execution_receipt.local_full_pool_execution_done=true` only means a button-gated local universe task consumed local rows and wrote a receipt. It must keep `production_full_pool_scan_done=false`, `provider_backed_acceptance_done=false`, `worker_backed_execution_done=false`, `legacy_retirement_ready=false`, and `legacy_fallback_required=true`.
- `deep_scan_local_review_receipt.local_deep_scan_review_done=true` only means a button-gated local review task inspected existing candidate evidence and gaps. It must keep `deep_scan_done=false`, `deep_scan_validation_done=false`, `provider_backed_acceptance_done=false`, `deepseek_called=false`, `worker_backed_execution_done=false`, `legacy_retirement_ready=false`, and `legacy_fallback_required=true`.
- `legacy_parity_acceptance_receipt.local_acceptance_receipt_ready=true` only means the old radar's no-feature-loss checklist is visible and locally guarded. It must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `legacy_fallback_required=true`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false` until worker execution, provider-backed parity, and browser visual/performance acceptance are complete.
- `production_radar_replacement_complete` remains false until real full-pool/deep-scan execution and provider-backed parity acceptance are complete.
- `result_delta_clarity_contract.local_result_delta_clarity_ready=true` means result-change cues are visible; `previous_cache_diff_done=true` is allowed only after comparing against a previous persisted radar packet, while `browser_visual_delta_qa_done=false` must remain explicit until browser visual QA is run.
- `candidate_browser_qa_runbook_contract.local_runbook_ready=true` only means the `#candidates` browser QA route/viewports/criteria are pinned; `visual_qa_complete` and `browser_performance_trace_done` remain false until an explicit browser run is reviewed.
- `candidate_browser_qa_evidence_summary.local_browser_qa_evidence_found=true` only means a local ignored runner report for `#candidates` was summarized. Even when `candidate_visual_qa_evidence_passed=true` and `candidate_browser_performance_evidence_passed=true`, `production_radar_replacement_complete=false` and `legacy_retirement_ready=false` must remain until real full-pool/deep-scan execution and provider-backed parity acceptance are complete.
- `candidate_browser_qa_review_contract.local_browser_qa_review_ready=true` is allowed only after explicit POST review and complete local default/reduced-motion evidence, and still must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false`.
- A passing local Candidate Radar browser QA review must include both default-motion and reduced-motion `#candidates` evidence across desktop/laptop/tablet/mobile, zero review-required rows, no external/model/provider calls, no trade execution, and no mutation of `strategy action`.
- `scripts/candidate_radar_contract.py` passes in the push gate while still reporting `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `browser_performance_trace_done=false`, and `browser_visual_delta_qa_done=false`.
- Radar output does not become a buy instruction and does not modify `strategy action`.
- Future search-to-quant projection returns task progress, data source provenance, call ledger, factor support/suppress/neutral/missing rows, freshness status, DeepSeek status, and chart payload without calculating trade action in React.
- Future `live_light` radar/quant bootstrap is bounded to current target / current holdings / watchlist subset; full-pool and deep-scan execution remain explicit worker tasks and never page-render side effects.

### Forbidden

- Do not scan the full market on page load.
- Do not start full-pool or deep-scan execution from `live_light` page open; only bounded light bootstrap may be considered after opt-in.
- Do not treat a search-to-quant projection result as a buy/sell recommendation.
- Do not treat `full_pool_scan_plan` as full-pool scan completion.
- Do not treat `full_pool_local_execution_receipt` as provider-backed full-market acceptance, production worker completion, browser QA completion, or permission to remove the legacy fallback.
- Do not treat `deep_scan_plan` as deep scan completion or legacy radar replacement.
- Do not treat `deep_scan_local_review_receipt` as deep scan completion, DeepSeek/model execution, provider-backed parity, production worker execution, browser QA completion, or permission to remove the legacy fallback.
- Do not treat `legacy_parity_acceptance_receipt` as production radar replacement, provider-backed acceptance, browser QA completion, or permission to remove the legacy fallback.
- Do not reduce legacy radar signal coverage without marking the gap.
- Do not hide candidate display truncation or local pool input truncation.
- Do not treat `no_feature_loss_acceptance_contract` as proof of production radar replacement.
- Do not treat `replacement_gap_triage_contract` as proof of legacy radar retirement readiness unless `legacy_retirement_ready=true` and every blocking gap is resolved by direct evidence.
- Do not treat `quick_scan_execution_receipt` as production replacement, provider-backed parity, browser performance proof, full-pool scan completion, or deep-scan completion.
- Do not treat `candidate_radar_production_activation_receipt` as production replacement, worker execution, provider-backed parity, durable browser/CI evidence, legacy retirement readiness, or a buy-signal approval.
- Do not treat `result_delta_clarity_contract` as browser visual QA or production radar replacement. Do not treat previous-cache diff as complete unless `previous_cache_diff_done=true` and `previous_cache_diff_rows` are present.
- Do not treat `candidate_browser_qa_evidence_summary` as CI evidence, provider-backed parity, legacy retirement readiness, or production radar replacement.
- Do not treat `candidate_browser_qa_review_contract` as browser execution, CI evidence, provider-backed parity, legacy retirement readiness, or production radar replacement.
- Do not treat `scripts/candidate_radar_contract.py` passing as full-pool scan, deep scan, provider-backed parity acceptance, browser performance proof, visual QA, legacy retirement readiness, or production radar replacement.
- Do not call Tushare/DeepSeek/GitHub from GET cache or render.
- Do not call unlabelled intraday providers; every source must be identified, mode-gated, and logged with safe request/response metadata.
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
- Metric tiles and packet cards now expose `visual_hierarchy_clarity` cues: finite, non-interactive CSS highlights make dense audit pages easier to scan without covering text, changing packet values, recomputing frontend state, or creating trade urgency.
- Packet cards now expose `packet_status_clarity`: `ready/success` states map to good visual tone, `pending/partial/review` states map to warning tone, and `blocked/failed/missing` states map to bad tone. The card border/hierarchy cue and `StatusBadge` share the same tone so dense dashboards make blocked or pending modules visible faster without changing packet data.
- `scripts/motion_viewport_qa_contract.py` now pins the LTG-14 browser QA route/viewport matrix and is run by `scripts/push_gate_3_0.sh`; it is a local static contract and still reports `visual_qa_complete=false`.
- `scripts/motion_browser_qa_runbook.py` now pins the local browser QA runbook: manual FastAPI/Vite startup order, local-only URLs, route/viewport matrix, ignored artifact path, visual acceptance criteria, reduced-motion pass, and performance budgets. It is run by `scripts/push_gate_3_0.sh` but does not open a browser, write screenshots, or prove visual/performance acceptance.
- Next-session ECharts now has a short update clarity layer and respects reduced-motion preferences by disabling chart update animation.
- Candidate radar now tags its primary result cluster with cache/coverage/blocker/degraded state so result transitions are visually easier to follow without recomputing candidates.
- Candidate radar now exposes `result_delta_clarity_contract` and `previous_cache_diff_rows` so candidate counts, skipped reasons, provider gaps, freshness, truncation, scan mode, local previous-cache candidate changes, and full/deep boundaries are visibly auditable before any browser visual QA is claimed.
- Current motion is CSS-only, finite-duration, and visual-only; it does not change packet values, task behavior, strategy action, or external-call boundaries.
- Call Ledger Audit now exposes `motion_clarity_audit` and `motion_clarity_rows`, a local static source audit for motion tokens, finite keyframes, navigation/status context cues, reduced-motion CSS/runtime behavior, StateClarityRail usage, chart/radar clarity scopes, layout containment, no timer/RAF motion loops, and no provider invocation markers.
- Call Ledger Audit now exposes `motion_production_qa_contract` and `motion_production_qa_rows`, a local production acceptance checklist for purposeful motion tokens, state-change clarity, chart/radar scopes, reduced-motion accessibility, layout readability, no timer/RAF loops, browser visual QA, performance trace, and provider/trade isolation. It keeps `production_motion_complete=false` until browser visual and performance checks are run.
- Call Ledger Audit now exposes `motion_keynote_roadmap_audit` and `motion_keynote_roadmap_rows`, a local route map for Apple-keynote-grade but restrained motion. It breaks the polish goal into state-clarity foundation, route staging, chart/radar delta choreography, task feedback microinteractions, dense-data readability, reduced-motion accessibility, performance trace promotion, visual-evidence promotion, and no-trade-urgency boundaries while keeping `production_motion_complete=false`.
- Call Ledger Audit now exposes `motion_browser_qa_runbook_contract`, `motion_browser_qa_runbook_rows`, and `motion_browser_qa_matrix_rows`, so the future browser pass has stable local routes, viewport rows, performance-budget rows, artifact policy, and safety boundaries before any visual QA is claimed.
- `scripts/motion_browser_qa_runner.mjs` now provides an explicit local browser QA runner for the pinned route/viewport matrix. It must be run manually after local FastAPI and Vite are started; it writes ignored artifacts under `.stock_ming_3/motion_qa`, starts no services, calls no providers/models/GitHub, and does not execute trades.
- Call Ledger Audit now exposes `motion_browser_qa_evidence_contract` and rows. It summarizes ignored local runner reports under `.stock_ming_3/motion_qa`, including default-motion and reduced-motion pass state, matrix counts, console errors, and performance verification flags, without committing screenshots or report artifacts.
- `POST /api/audit/motion-browser-qa-review` now creates a button-gated local review task for ignored motion browser QA reports. It records `motion_browser_qa_review_contract` and rows, requires explicit POST before `explicit_review_task_done=true`, and still keeps CI evidence, browser visual QA promotion, performance promotion, and `production_motion_complete` blocked.
- Call Ledger Audit now exposes `motion_production_activation_receipt` and `motion_production_activation_rows`: this local activation receipt converts the static motion audit, production QA checklist, keynote roadmap, browser QA runbook, ignored local evidence, explicit review task, visual promotion, performance promotion, durable CI evidence, and no-trade/no-action boundary into one next-step checklist. It keeps `production_motion_complete=false`, `visual_qa_complete=false`, `browser_performance_verified=false`, and `durable_ci_evidence_complete=false` until direct promotion evidence exists.
- On 2026-06-14, the explicit local browser runner completed two local passes after manual FastAPI/Vite startup: default motion passed 20/20 route-viewport rows with zero console errors, and reduced-motion passed 20/20 route-viewport rows with zero console errors. The button-gated Motion browser QA review reached `motion_browser_qa_review_ready_local_artifact` with zero blocking review rows in the same local app session. These reports are local ignored artifacts and still require durable review/promotion before production completion claims.
- Mobile layout now has a responsive breakpoint so navigation no longer squeezes Command Center content or state clarity rails on narrow screens. Local default-motion and reduced-motion browser runner reports can prove a specific run, but ignored local artifacts are not durable CI or production motion completion.
- Further polish should improve clarity without distracting from risk, freshness, and decision boundaries.

### Gaps

- Need browser-verified transitions for panel expansion and candidate-radar result deltas beyond the current local `result_delta_clarity_contract`, primary cluster, clarity rail, and static phase-confirm cue.
- Need broader chart motion verification so updates help users understand state changes instead of adding decoration.
- Need browser viewport execution against the pinned route/viewport matrix so animation never overlaps, occludes, or resizes critical text.
- Need runtime performance traces so later animation never reintroduces UI stalls.
- The browser QA runbook is executable planning evidence only; it is not itself a browser pass.
- Local browser reports now exist on the current workstation, but they are ignored artifacts rather than durable CI evidence. They can move `motion_browser_qa_evidence_contract` to evidence-available status locally, while `production_motion_complete=false` remains correct until evidence is reviewed and promoted.
- The Motion browser QA review task is now button-gated and local-only, but it reviews ignored local artifacts rather than running browser QA in CI or proving production motion completion.
- The explicit runner is available and has local pass reports, but runner availability and local ignored reports are still not the same as production motion completion.
- Need visual hierarchy that makes status, freshness, blockers, and candidate changes obvious.
- Visual hierarchy cues now exist statically, but they still need browser viewport review on dense pages before being treated as production polish.
- Packet status clarity now exists statically, but it still needs browser viewport review to prove good/warn/bad card cues remain readable across dense desktop and mobile pages.
- Current navigation/status cue layer improves static context visibility but still needs browser viewport review for dense pages and mobile widths.
- `motion_clarity_static_ready_visual_qa_pending` is not production motion completion; it only proves static source guardrails.
- `motion_production_qa_local_ready_visual_perf_pending` is also local QA only; it does not prove browser visual quality or runtime performance.
- `motion_keynote_roadmap_local_ready_promotion_pending` means the high-polish motion roadmap is visible and auditable; it does not run browser QA, promote ignored local artifacts, prove performance, or complete production motion.
- `motion_activation_receipt_ready_production_blocked` means LTG-14 has a clear next safe path; it still does not run the browser runner, perform button-gated review, promote visual/performance evidence, create durable CI proof, or complete production motion.

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
- Metric/card visual hierarchy cues are finite, pointer-safe, reduced-motion bounded, and audited as visual-only scanability aids.
- Packet card status tone makes ready/pending/blocked states visible without changing packet values, action, urgency, or sorting.
- The motion viewport QA contract is repeatable in the push gate, while browser execution remains explicit and pending.
- The motion browser QA runbook is repeatable in the push gate and fixes local URLs, artifact policy, route/viewport matrix, visual criteria, reduced-motion pass, and performance budgets without opening a browser.
- The explicit browser QA runner exists and is audited as explicit-only: it opens only local `127.0.0.1` routes after services are already running, writes ignored local artifacts, and is not run by GET cache or default push gate.
- `motion_browser_qa_evidence_contract` can summarize default and reduced-motion reports when local ignored artifacts exist; it must keep `production_motion_complete=false` until those reports are reviewed and intentionally promoted.
- `motion_browser_qa_review_contract.local_browser_qa_review_ready=true` is allowed only after explicit POST review and complete local default/reduced-motion evidence, and still must keep `production_motion_complete=false`, `browser_visual_qa_promoted=false`, `browser_performance_promoted=false`, and `ci_evidence_complete=false`.
- Visual polish is additive and does not replace audit labels, warnings, or freshness state.
- `motion_production_qa_contract.local_motion_qa_ready=true` only means the local production checklist is visible and source guardrails pass; visual QA and performance trace must remain pending until explicitly executed.
- `motion_keynote_roadmap_audit.roadmap_ready=true` only means the Apple-keynote-grade polish roadmap is locally organized. `production_motion_complete`, `browser_visual_qa_promoted`, `browser_performance_promoted`, and `durable_ci_evidence_complete` remain false until explicit promotion evidence exists.
- `motion_browser_qa_runbook_contract.local_runbook_ready=true` only means the execution checklist is ready; it is not screenshot evidence, performance trace evidence, or production motion completion.
- `motion_production_activation_receipt.local_activation_receipt_ready=true` only means the next safe sequence is explicit local browser runner, button-gated local review, durable visual/performance promotion, and CI/release evidence. It is not browser execution, CI evidence, visual promotion, performance promotion, or production motion completion.
- `motion_clarity_audit.static_ready=true` is allowed only when static source checks pass.
- `production_motion_complete` remains false until browser viewport and performance QA are complete.

### Forbidden

- Do not add decorative motion that obscures evidence, warnings, or risk state.
- Do not use hierarchy cues to imply urgency, certainty, or a buy/sell recommendation.
- Do not animate by recomputing backend data.
- Do not use motion to imply certainty, urgency, or trade recommendations.
- Do not regress text readability or viewport layout.
- Do not treat the browser QA runbook as an executed browser pass.
- Do not treat runner availability as visual QA completion; only a reviewed runner report can move browser visual/performance evidence forward.
- Do not commit `.stock_ming_3/motion_qa` reports, screenshots, or videos as production proof.
- Do not treat local ignored QA reports as CI evidence or production motion completion without explicit review and promotion.
- Do not treat `motion_browser_qa_review_contract` as browser execution, CI evidence, visual QA promotion, performance promotion, or production motion completion.
- Do not treat `motion_production_activation_receipt` as browser execution, durable CI evidence, visual QA promotion, performance promotion, or production motion completion.

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
| P2a | 运行模式分层与 `live_light` bootstrap | Keep `cache_only` safe while designing opt-in light startup tasks for local daily research. |
| P3 | Factor Test Lab 真实小股票池研究 | Promote from light research metrics to research-grade validation. |
| P3a | 下一票雷达快扫生产化 | Restore radar scan capability in 3.0 without UI stalls or signal loss. |
| P4 | Storage / Worker 生产化 | Make heavy work reliable and auditable. |
| P5 | DeepSeek pro 稳定性提升 | Improve JSON stability while keeping manual/default-off governance. |
| P6 | Tauri production package | Turn dev/preflight shell into user-openable desktop package. |
| P7 | Streamlit 完全退场 | Move ordinary workflows to Command Center 3 after replacement is ready. |
| P8 | 动效与可视化清晰度优化 | Add polished motion after core data, worker, and desktop paths are stable. |

## Risk Boundaries

- `cache_only` 是默认安全模式；cache API、FastAPI 启动、React 初始 render 不自动外联。
- GET cache API 不直接调用 Tushare / DeepSeek / GitHub。
- React render 不直接调用 Tushare / DeepSeek / GitHub。
- POST task / worker / local fallback 才可能外部调用，且必须有模式、按钮或显式 payload 门控。
- `manual` 模式只允许用户点击按钮或提交显式任务后外联。
- `live_light` 模式可以在初始 cache render 后创建一次限频后台 bootstrap task，用于轻量 Tushare 刷新和可选 DeepSeek pro 解释；这不是 render 直接外联。
- `live_light` 默认关闭，必须可配置、可见、可审计、可跳过、可失败降级。
- `live_full` 预留；全池/深扫不默认启用。
- GitHub probe 不在页面启动时自动调用；如后续进入 `live_light`，仍需独立按钮或显式 task mode。
- DeepSeek 不作为数据源。
- Factor 分数不直接改 `strategy action`。
- 下一票雷达不在页面启动时做全市场扫描；`live_light` 只能覆盖当前标的/持仓/watchlist 的有界轻量任务。
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
