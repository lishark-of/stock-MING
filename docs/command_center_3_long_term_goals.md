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

用户确认的运行模式口径：边界问题不是安全线“太强硬”，而是安全线必须分层。默认模式仍应像离线/cache 审阅面板一样安全；本地日常投研客户端则可以在用户明确配置后，于页面已经用 cache 渲染完成之后，启动一次轻量后台任务。

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

The safe default remains fully offline at startup. A local user may intentionally opt into daily research automation by setting:

```text
COMMAND_CENTER_BOOTSTRAP_MODE=live_light
COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN=true
COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN=true
```

When this is enabled, the UI must show the active mode and automation switches in plain sight: current runtime mode, Tushare auto refresh on/off, DeepSeek pro auto explanation on/off, latest bootstrap task id/status, skipped-by-rate-limit state, and safe error text when a task fails.

`live_light` target behavior is intentionally narrow: the page must render from cache first, create at most one background bootstrap task inside the rate limit, show the current mode and task status, and degrade safely when the task fails. The task may refresh current target / holdings / watchlist light data, refresh factor and next-session caches, and optionally enqueue a governed DeepSeek pro explanation after data is ready. It must not block UI, mutate `strategy action`, change prices or holdings, write `operation_zones`, execute trades, or expose token/key material.

`live_light` therefore changes the old "startup never automates anything" rule into a mode-layered rule: startup automation is forbidden in `cache_only`, manual in `manual`, and allowed only as an auditable background POST task in `live_light`. React may request the task after the first cache render, but React still never calls Tushare, DeepSeek, GitHub, Python modules, or adapters directly.

以下两句话必须同时成立：

- GET cache, FastAPI startup, and the initial React render do not call Tushare, DeepSeek, GitHub, intraday providers, or broker/trading adapters.
- In `live_light`, React mounted behavior may create one rate-limited `POST /api/bootstrap/live-startup` task. Any Tushare refresh, DeepSeek pro explanation, or intraday adapter read must happen behind that task boundary with `call_ledger` / `model_ledger` evidence, safe errors, visible mode state, and no trade/action mutation.

Target `live_light` bootstrap scope:

| area | allowed in `live_light` | required boundary |
|---|---|---|
| Tushare light refresh | `trade_cal` if needed, `daily`, `daily_basic`, `moneyflow` for current target / holdings / watchlist, default capped at 20 symbols | POST task only, `call_ledger`, safe errors, no token exposure |
| Staged market evidence | margin, limit/emotion, chip, dragon-tiger, disclosure, hard-risk groups | opt-in payload/config only; matrix or no-record rows are not negative evidence |
| DeepSeek pro explanation | optional after Tushare / factor / next-session cache is ready | model ledger, input/output hash, sanitizer, parse-failed discard, no numeric/action overwrite |
| Search / radar quant projection | a searched symbol or bounded watchlist subset can create a one-shot task for "生成 3.0 量化推演" / "一键生成量化投研图谱" | no full-pool or deep-scan on render; progress and gaps must stay visible |
| Intraday or realtime evidence | allowed only through configured provider adapters when Tushare is insufficient | provider identity, freshness, call ledger, mode gate, and safe error are mandatory |

`live_light` provider/model ledger minimums:

| surface | required audit fields | explicit non-goals |
|---|---|---|
| Tushare | `api`, `provider`, `request_params_safe`, `row_count`, `data_date`, `local_fetched_at`, `call_status`, `error_message_safe` | no token exposure, no unselected API marked verified, no `no_record` as negative evidence |
| DeepSeek pro | `model_used`, `status`, `token_usage`, `parse_status`, `cache_hit_or_miss`, `input_hash`, `output_hash` | no data-source role, no price/holding/factor/action/operation-zone overwrite, no buy/sell instruction |
| Intraday adapter | provider id, freshness, request context, safe error, mode gate, ledger row | no unidentified mixed data source, no page-render provider call |

This mode layering also applies to search-driven research. A future stock search or "生成 3.0 量化推演" action should create a POST task that validates the symbol, refreshes allowed light data, writes call ledger/model ledger, updates Factor Quant Hub and Next Session cache, and displays provenance, freshness, DeepSeek status, and chart results. It remains research-only and cannot turn DeepSeek text, factor scores, or radar candidates into buy/sell instructions.

Unified search-to-quant projection target: after the user enters or searches a symbol, Command Center 3 should expose a single clear action such as "一键生成量化投研图谱" or "生成 3.0 量化推演". That action must validate the symbol, run only the allowed light refresh scope, build `call_ledger` and `model_ledger` rows, update Factor Quant Hub / Next Session / ECharts cache, and show task progress, data provenance, factor support/suppress/neutral/missing rows, freshness state, DeepSeek status, and chart results. It must not run full-pool/deep-scan on render, hide provider gaps, or turn the projection into a trade instruction.

Current implementation checkpoint: `GET /api/bootstrap/status` now exposes the runtime mode cache, safe configuration rows, mode rows, and `live_light` policy. `POST /api/bootstrap/live-startup` is registered as a local task skeleton; Settings / Config Health can create it manually, and Command Center Home can create it once after first cache render when `COMMAND_CENTER_BOOTSTRAP_MODE=live_light` and sources are enabled. The skeleton now records a staged run plan and DeepSeek model-ledger preview so future provider/model execution has an auditable shape before it is enabled. This is still local-only: it records mode, rate limit, session dedupe, payload-safe request context, task status, call ledger, stage rows, model-ledger preview rows, and no-external-call summary, but it does not call Tushare/DeepSeek/GitHub, does not read token/key values, and keeps `provider_execution_implemented=false`.

`scripts/bootstrap_runtime_contract.py` is now part of the local push gate. It validates `cache_only`, `live_light` with sources disabled, and `live_light` with Tushare/DeepSeek switches enabled while keeping provider/model execution pending. The contract proves the staged plan, model-ledger preview, rate-limit reuse, symbol cap, payload sanitization, no provider/model/GitHub calls, no real trades, and no `strategy action` mutation remain visible before future execution is enabled.

`GET /api/bootstrap/status` now also exposes `provider_linkage_rows`: a runtime linkage audit for cache/render, `live_light` POST bootstrap, Tushare light refresh, DeepSeek pro after-task explanation, GitHub probe, and real-trading boundaries. Command Center Home and Settings / Config Health display these rows so the Tushare/DeepSeek linkage state is visible before provider execution is implemented. This audit is still local/read-only and keeps Tushare/DeepSeek/GitHub calls false.

`GET /api/migration/status` now also exposes `tushare_deepseek_linkage_rows`, a roadmap-level layer audit for cache/render silence, `live_light` POST task creation, Tushare provider execution, DeepSeek pro after-task execution, GitHub probe exclusion, production promotion, and real-trading isolation. This makes the 14-goal planning page show exactly which linkage layer remains pending before real provider/model acceptance. It is cache-only/read-only and keeps Tushare/DeepSeek/GitHub calls false.

`POST /api/migration/tushare-deepseek-linkage-review` now records a button-gated local linkage review receipt over the same four layers. The receipt makes missing real Tushare call ledger, optional DeepSeek model ledger, browser non-blocking evidence, redaction review, and production promotion evidence visible, while keeping provider/model execution, GitHub probe, real trading, token/key exposure, and production promotion false. `GET /api/migration/status` may replay the latest receipt metadata, but it does not create tasks or call external services.

`GET /api/bootstrap/status` now also exposes `live_light_activation_receipt` and `live_light_activation_rows`. This receipt is the next-step checklist between linkage visibility and real provider/model execution: mode layering, cache/render silence, POST task boundary, rate limit, symbol cap, call/model ledger requirements, GitHub exclusion, full-pool reserve, token/key boundary, and real-trading isolation are visible; Tushare provider execution, DeepSeek model execution, and production promotion remain explicitly blocked. It is ready for provider/model execution design, not ready for provider/model execution.

`GET /api/bootstrap/status` now also exposes `live_light_provider_model_acceptance_runbook` and rows. This runbook fixes the future user-approved real acceptance sequence: mode/scope preflight, explicit approval, server-side secret presence check without value exposure, `trade_cal`, `daily/daily_basic/moneyflow`, local factor/next-session refresh, optional DeepSeek pro model ledger, UI non-blocking evidence, ledger redaction/safety review, and production promotion review. It is a local runbook only: provider/model execution, browser runtime evidence, and promotion evidence remain pending.

`POST /api/bootstrap/provider-model-acceptance-dry-run` now creates a user-approved local acceptance dry-run task before any real provider/model run. It consumes the runbook, sanitizes payloads, caps symbols, allows only `trade_cal / daily / daily_basic / moneyflow`, reports ignored APIs, checks only whether required server-side environment keys exist, records phase rows and call ledger, and keeps Tushare/DeepSeek/GitHub calls false. It reports credential presence as booleans and safe credential labels only; it does not return raw env key names, read values, return values, hash values, log values, or expose token/key material. Missing required credential presence now blocks the dry-run from being marked ready for user-approved real acceptance while still recording a successful local preflight task. The dry-run summary also exposes `allowed_next_step`, `missing_evidence_items`, and `not_allowed_next_steps` so the path to real provider/model acceptance cannot skip user approval, credential presence, call/model ledger evidence, redaction review, or production promotion review. It also records a SHA-256 `acceptance_scope_ticket` over safe scope fields such as mode, route, symbols, selected APIs, provider/model switches, model name, symbol limit, approval state, and credential-presence status; this ticket lets future user confirmation bind to the exact dry-run scope without including env key names or credential values. This is an auditable preflight gate, not provider-backed or model-backed acceptance.

The same dry-run now records `real_acceptance_preflight_receipt` and rows. This receipt keeps real execution blocked even when the dry-run scope is approved and credentials are present, until a separate explicit real provider/model task exists and records real Tushare call ledger, DeepSeek model ledger, browser non-blocking evidence, ledger redaction review, and production promotion evidence. It is a local preflight receipt only: `ready_to_execute_real_task=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, `production_live_light_complete=false`, and all Tushare/DeepSeek/GitHub call flags remain false.

Mode-layered acceptance contract from the latest user baseline:

- The boundary is not "never automate anything"; it is `cache_only` default-deny plus explicit upgrades to `manual` or `live_light`.
- `cache_only` remains the only acceptable mode for smoke, CI, quick offline review, and no-network runs. It must not create bootstrap tasks, call providers, call models, ping GitHub, or inspect secrets.
- `manual` remains the safest research mode: Tushare, DeepSeek, GitHub probe, intraday adapters, and heavy scans require an explicit button or submitted task payload.
- `live_light` may become the local daily research-client mode: after the first cache render, React may create one rate-limited background bootstrap task. That task may refresh bounded Tushare light data and optionally enqueue DeepSeek pro after data readiness. It must remain capped, deduped, non-blocking, ledgered, and safe to fail.
- `live_light` is not production provider/model execution until the task records real provider call ledger and model ledger evidence. The current skeleton, staged run plan, provider linkage rows, and sanitizer checks remain scaffold/preflight/audit states.
- `live_full` is reserved for full-pool, deep-scan, and production worker orchestration. It must not be enabled by page render or hidden defaults.

The first production-shaped `live_light` implementation should preserve this exact scope: current target / current holdings / watchlist or a searched symbol, default maximum 20 symbols, `trade_cal` when needed, `daily`, `daily_basic`, `moneyflow`, optional staged interfaces only by payload/config, and optional DeepSeek pro with same-input hash dedupe, model ledger, six-field sanitized output, parse-failed discard, and no price/holding/factor/action/operation-zone overwrite.

Required mode-layering tests before any real `live_light` provider/model promotion:

- `cache_only`: page startup creates no bootstrap task; GET cache and initial React render stay provider/model/GitHub silent.
- `live_light`: page startup can create one background task after cache render, respects rate limit/session dedupe, never blocks UI, and reports safe failure.
- Tushare: mock or provider-backed acceptance rows record call ledger, distinguish permission denied / no record / empty window / parse error / stale states, and never expose token.
- DeepSeek: optional after-task execution uses configured model name, input hash dedupe, sanitizer, parse-failed fallback, no trading language, and no numeric/action overwrite.
- Search-to-quant projection: a searched symbol creates a task, exposes task id/progress/provenance/freshness/DeepSeek status/ECharts result, and never starts full-pool or deep-scan work from render.

Documentation wording rule for this baseline: do not describe the boundary as a flat "page startup never calls providers" once `live_light` is in scope. Future docs, tests, and review notes must name the layer being discussed: `cache_only` startup/render silence, React-created POST task, provider/model execution inside that task, and production acceptance evidence. A `live_light` task creation is allowed only after cache render and only when explicitly configured; a real provider/model call is a separate acceptance step; production completion still requires direct call/model ledger evidence and promotion review.

User wording checkpoint for future reviews: the boundary is being upgraded from an absolute startup ban to runtime-mode layering, not weakened into hidden automation. `cache_only` remains the default offline/smoke/CI posture. `manual` remains explicit button/task operation. `live_light` may support the local daily research-client experience by creating one visible, rate-limited background task after cache render, but provider/model execution still needs safe configuration, POST-task audit trails, call/model ledger evidence, no UI blocking, no `strategy action` mutation, no real trading, and no token/key exposure. Reviewers should judge each change by its layer: initial render silence, task creation, real Tushare/DeepSeek execution, and production promotion are four different checkpoints.

Latest user wording distilled into this roadmap: the long-term goal is not to keep Command Center 3.0 permanently offline, but to make every external-capable path mode-aware and reviewable. In `cache_only`, startup and render stay fully quiet. In `manual`, a human click or explicit task payload is the trigger. In `live_light`, the local research-client path may create one bounded bootstrap task after cache render, covering current target / holdings / watchlist / searched symbol, but only with visible mode state, symbol caps, rate limits, provider/model ledgers, safe failure, no hidden full-pool scan, no trading chain, and no token/key exposure. Any future wording or implementation should preserve that distinction instead of flattening the boundary back into either "never automate" or "silently automate".

## Remaining Goals Snapshot

Current snapshot date: 2026-06-16.

Strict completion status: none of the 14 long-term goals should be closed as fully complete yet. LTG-11 and LTG-12 are the closest to stable operating policy, but they still remain ongoing release boundaries rather than one-time completed features.

Progress summary as of 2026-06-16: the Command Center 3.0 migration foundation is roughly 70-75% established, while production acceptance across the 14 LTGs is roughly 25-35% complete. The strict closeout count remains `0 / 14` because every LTG still has at least one provider-backed, packaged-runtime, browser-performance, worker/storage, or retirement acceptance item pending.

| bucket | count | goals | current meaning |
|---|---:|---|---|
| Mostly stable guardrails | 2 | LTG-11, LTG-12 | Local gate and real-trading isolation are working release boundaries, but must keep running on every push candidate. |
| Real validation still required | 5 | LTG-01, LTG-02, LTG-03, LTG-04, LTG-13 | The codebase has local contracts, scaffolds, or light paths, but production acceptance still needs real provider data, real pools, or browser/performance proof. |
| Productionization still required | 5 | LTG-05, LTG-06, LTG-07, LTG-08, LTG-09 | Storage, worker, model explanation, chart parity, and desktop package have useful preflight/contracts, but are not production complete. |
| Dependent retirement goal | 1 | LTG-10 | Streamlit can only exit ordinary workflow after React/Tauri parity and fallback safety are proven. |
| Later polish goal | 1 | LTG-14 | Motion clarity should continue after core data, worker, desktop, and radar validation are stable. |

Migration Status now includes a read-only `14 LTG acceptance runway` view backed by `GET /api/migration/status` field `ltg_acceptance_runway_rows`. It derives each LTG row's priority, completion bucket, completion estimate, observed pending count, next step, and closeability from the existing roadmap/cache payloads so the next P0-P10 acceptance work is visible without rereading the full document. The same summary exposes hard closeout fields (`strict_closeout_done_count`, `strict_closeout_total_count`, and `strict_closeout_remaining_count`) so percentage estimates cannot be mistaken for closed production LTGs. This runway does not create tasks, call providers/models/GitHub, execute trades, mutate actions, or close any LTG; it is a planning and audit surface only.

`scripts/ltg_progress_snapshot.py` is now the local acceleration entrypoint for 14-LTG work. It prints the same strict closeout count, per-LTG completion estimates, next local queue rows, clean local-button readiness, durable handoff readiness, and cache-only safety flags from `build_migration_status()` without starting FastAPI, calling Tushare/DeepSeek/GitHub, opening a browser, creating tasks, executing trades, reading secrets, or closing any LTG. Future development turns should use this snapshot first, then work one small evidence-bound LTG slice at a time instead of re-reading the full long-term document.

Migration Status also exposes `ltg_next_acceptance_action_rows`, a near-term execution navigation table now covering all 14 LTGs. It names the next explicit POST routes for `trade_cal` provider acceptance, staged Tushare target samples, Factor Test Lab small-pool provider validation, Factor universe worker-batch scope tickets / execution requests / local research receipts, Candidate Radar provider/worker promotion, Storage physical execution request, Worker runtime QA scope tickets, DeepSeek provider benchmark scope ticket, next-session browser QA review, and motion promotion dry-run, while LTG-11 release gate and LTG-12 trade isolation remain read-only release-invariant rows. It also reads local task metadata through `task_service.list_task_statuses` plus local storage/worker/candidate/factor/next-session/desktop/legacy/audit/risk packets to show whether each dry-run / execution-request / promotion / runtime QA / model scope-ticket / browser QA review / package readiness / retirement readiness / release gate / trade-isolation receipt is already visible, which local step is still missing, and the next safe local route to run. The same rows now include `next_local_step_preview_rows`, which summarize the safe payload shape, required prior receipt/material, known disable reason, and no-provider/no-worker/no-model/no-browser/no-trade boundary before a button is clicked. For LTG-02 target-sample execution requests, the preview may prebind the latest local `provider_target_sample_execution_recipe` short scope hash, requested target groups, and selected APIs from `command_center_tushare_refresh_packet`; this only enables a clean local execution-request ticket and still does not create the future provider task or call Tushare. For LTG-04 Factor universe worker-batch, the queue can now generate local scope-ticket, execution-request, and research-receipt records; it still does not start workers, ping Redis/Celery, read storage, compute full-pool rank/zscore/neutralization, or complete production universe research. For LTG-13 Candidate Radar promotion dry-runs, the preview may prebind the latest local production replacement review scope hash from `command_center_3_candidate_radar_cache`; this only enables a clean promotion dry-run ticket and still does not start workers, call Tushare/DeepSeek, run browser QA, retire legacy radar, or complete production replacement. For LTG-05/LTG-06, the queue replays Storage physical execution request and Worker runtime QA receipts from SQLite packets as scope evidence only; it still does not write Parquet/manifests, delete artifacts, start Celery/Redis, dispatch runtime QA, or complete production storage/worker. For LTG-07/LTG-08, the queue can generate only a local DeepSeek benchmark scope ticket or read-only next-session browser QA review receipt; it still does not call DeepSeek, open a browser, generate artifacts, prove Streamlit parity, or complete production replacement. For LTG-11/LTG-12, the queue only exposes release-gate and research-client trade-isolation receipts; it does not run `scripts/push_gate_3_0.sh`, call GitHub, push, connect broker/order APIs, approve paper trading, or create trading controls. Once a local execution-request receipt is ready, `future_handoff_preview_rows` can show the future provider/worker/storage route, target task type, target acceptance mode, selected APIs, target groups, symbol/date context, and source local task id as a read-only handoff checklist; it still requires a separate user-approved provider/worker/storage task and is not provider execution, physical execution, worker runtime evidence, CI evidence, or real-trading evidence. Handoff ready now also requires the local execution-request receipt to be visible from SQLite durability (`sqlite_meta` or `memory_and_sqlite`); memory-only task state is shown as temporary and cannot be used as cross-process acceptance evidence. Blocked local receipts are counted separately and do not advance the queue to the next phase. The React page summarizes observed/missing local receipts, local step rows, preview rows, handoff previews, durable receipt counts, memory-only receipt counts, ready/blocked receipt counts, and ready local buttons before the raw table, so the next acceptance move is visible without treating JSON metadata as production evidence. The same page can launch only an allowlisted local dry-run / execution-request / promotion-review / scope-ticket / artifact-review route from the next-action queue, and it disables known blocked submissions when a prior local receipt, scope hash, review hash, or execution-request task id is missing; that button path still records a local receipt only, does not call provider/model/GitHub services, does not start workers, does not execute trades, and cannot close any LTG without the direct provider/worker/model/browser/storage/CI/trade-isolation evidence listed in the row.

The queue now separates required local receipt steps from durable production evidence recipes. For example, after the LTG-04 worker-batch dry-run, execution-request, and local research receipt are durable and ready, the queue can move to future worker runtime / storage / metric / promotion evidence while the durable evidence recipe still records production blockers for real worker execution, rank/zscore, neutralization, full-pool validation, and promotion. This is progress in the local audit chain, not production completion.

Quota guidance while weekly budget is low: do not start broad new development when the remaining weekly quota is around 20%. Prefer final push-gate review, user-confirmed push, and short documentation handoff. Resume P1-P5 validation work after quota resets or when a narrow acceptance run is explicitly requested.

## Long-Term Goals Table

| id | long_term_goal | current_status | target_state | priority | success_criteria |
|---|---|---|---|---|---|
| LTG-01 | A 股交易日历级 freshness 生产化 | `done_real` MVP; provider acceptance runbook/receipts, local `trade_cal` scope ticket dry-run, bound execution-request ticket, local promotion-review receipt, latest ticket/review cache visibility, producer generation/cache-refresh readiness, producer cache-refresh execution-request ticket, local SQLite-only producer cache refresh task, production stage-scope manifest, and durable evidence recipe exist; provider-backed validation still pending | All current evidence is gated by expected trade date | P1 | stale / expired / historical / unknown data cannot enter score, support, evidence preview, or action; real `trade_cal` promotion requires direct provider-backed evidence. |
| LTG-02 | Tushare 全接口生产流水线 | core light path `done_real`; extended APIs `matrix` / `mock`; interface-group acceptance scope, production stage-scope manifest, `live_light` status contract, local bootstrap skeleton, staged run plan, model-ledger preview, provider/model runbook, local acceptance dry-run, `trade_cal` promotion-review receipt, Tushare/DeepSeek linkage review receipt, target-sample execution recipe, scope-bound target-sample execution-request ticket, latest target-sample request cache visibility, React Data Health target-sample request visibility, and durable evidence recipe exist; provider execution remains pending | All selected interfaces run through task pipeline with call ledger and mode-gated refresh rules | P2 | Each interface has real target samples, safe failure states, no false verified claims, no cache/render direct provider calls, and direct evidence before production promotion. |
| LTG-03 | Factor Test Lab 完整生产化 | light research metrics `done_real`; production QA / provider blocker receipts, required metric-scope manifest, production stage-scope manifest, provider small-pool dry-run scope ticket, execution recipe, and durable evidence recipe exist; provider-backed production research incomplete | Research-grade factor validation for single factors | P3 | IC, Rank IC, ICIR, groups, cost, drawdown, sample split, decay, and neutral IC are auditable and research-only until a separate real provider-backed small-pool validation passes. |
| LTG-04 | Factor 全市场 / 股票池研究 | light mode plus local read-plan, readiness/activation receipts, local rank/zscore sufficiency audit, worker-batch dry-run scope ticket, execution recipe, bound execution-request ticket, local research receipt, worker stage-scope manifest, and durable evidence recipe; real worker runtime/storage/metric execution pending | watchlist / custom pool / full pool research pipeline | P3 | Large universe runs in task pipeline without blocking UI or entering strategy action. |
| LTG-05 | Storage / DuckDB / Parquet 生产化 | dataset scaffold, dry-runs, query policy, physical execution recipe, stage-scope manifest, and push-gate contract exist | Versioned, queryable local data layer | P4 | schema/version/TTL/compaction/query services are auditable; physical execution is evidence-bound; data artifacts stay out of git. |
| LTG-06 | Worker / Celery / Redis 生产化 | local task fallback, preflight, blocker audit, healthcheck QA contract, readiness/activation receipts, runtime QA execution recipe, durable evidence recipe, runtime evidence stage-scope manifest, and push-gate contract exist | Production-capable worker orchestration with local fallback | P4 | POST returns task_id, worker runs heavy jobs, Redis absence falls back gracefully, scheduler stays off by default, runtime QA and durable evidence are explicit. |
| LTG-07 | DeepSeek pro 稳定解释生产化 | manual governance, sanitizer, local JSON stability audit, response-format review, retry/repair dry-run, activation receipt, provider benchmark execution recipe, provider benchmark scope-ticket POST preflight, Tushare/DeepSeek linkage review receipt, production stage-scope manifest, and push-gate contract exist; mini-benchmark below production target; `live_light` auto explanation remains future work | Stable manual explanation, optional mode-gated background explanation after data tasks | P5 | JSON success rate > 90%, no action leakage, no numeric overwrite, cost predictable, and failed parse never contaminates packets. |
| LTG-08 | ECharts 次日操作图谱成熟版 | maturing chart contract with interaction readiness audit, no-feature-loss legacy parity recipe, and production replacement stage-scope manifest; legacy parity pending | React/ECharts replaces Streamlit main next-session visual | P5 | Complete cache display, evidence interactions, no frontend action/price/position mutation, no legacy signal-group loss. |
| LTG-09 | Tauri desktop production package | dev/preflight with runtime contract, local 3.0 double-click launcher contract, local executable release binary QA, and production package stage-scope manifest; `.app`/DMG packaged runtime QA pending | Production desktop shell for ordinary users | P6 | tauri dev/build pass; backend-offline state is friendly; config/log policy is validated; token/key never enters frontend. |
| LTG-10 | Streamlit 完全退出普通主流程 | `legacy/admin/debug` marked, fallback dependency contract and retirement stage-scope manifest visible, still used for fallback | Streamlit only for debug/admin/fallback | P7 | Ordinary research workflow runs through Command Center 3 desktop. |
| LTG-11 | 测试 / CI / smoke / 安全扫描标准化 | local tests, smoke, local contract guards, CI mirror, push readiness receipt, and release gate stage-scope manifest exist | Repeatable gate for every release candidate | P0/P4 | unittest, frontend build, smoke, diff check, secret scan, artifact scan, and local LTG contracts are documented and enforced. |
| LTG-12 | 真实交易链路继续保持隔离 | auto trading not connected; local trade-isolation stage-scope manifest exists | Trading remains explicitly out of automatic chains until a separate real-trading project passes every required stage | Always | No automatic order path; strategy action cannot be mutated by research/cache/model/frontend paths; future trading work is mode-tiered and evidence-gated, not silently enabled. |
| LTG-13 | 下一票雷达快扫生产化 | local fast-scan readiness, fast-scan task-pipeline contract, no-feature-loss QA, legacy parity acceptance receipt, local full-pool execution receipt, local full-pool worker fallback route, local deep-scan review receipt, local deep-scan worker fallback route, search-to-quant projection local receipt, provider parity dry-run, worker execution recipe, scope-bound worker execution-request ticket, scope-bound searched-symbol provider/model execution-request ticket, durable evidence recipe, production stage-scope manifest, scope-bound production promotion dry-run, and push-gate contract exist; real Celery/Redis worker, provider-backed full-pool/deep-scan, DeepSeek/model-ledger execution, provider/model-backed quant projection execution, durable browser/CI promotion, and legacy retirement pending | Fast radar scan and search-driven quant projection in Command Center 3 without feature loss or degraded signal coverage | P3 | Radar and search tasks run through task pipeline, preserve legacy signal groups, avoid UI stalls, report coverage gaps instead of hiding them, and require direct worker/provider/model/browser/legacy-retirement evidence before production replacement. |
| LTG-14 | Command Center 3 动效与可视化清晰度优化 | first motion clarity layer, static readiness audit, production QA contract, local browser runner/review receipts, and production stage-scope manifest exist; durable browser visual/performance promotion pending | Apple keynote-grade clarity and restrained motion that makes state changes easier to see | P8 | Motion is purposeful, performant, accessible, respects reduced-motion, never obscures data or decisions, and requires direct visual/performance evidence before production completion. |

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
- Data Health now canonicalizes the global `data_freshness` cache context from existing local fields such as `state=today`, `last_updated`, and the local expected-date gate. This makes the global current-evidence freshness row auditable as `fresh` when its local date matches expected, while keeping `canonical_context_is_provider_acceptance=false`, `canonical_context_calls_provider=false`, and all Tushare/DeepSeek/GitHub/trading flags false.
- Producer coverage remains stricter than the global context: candidate radar, evidence radar, market context, Factor, and next-session producers must still carry their own explicit `expected_trade_date`, `data_date`, and `freshness_state` fields. The audit does not treat generic producer timestamps as data dates and does not backfill producer `expected_trade_date` as production proof.
- Command Center home snapshot producer builders now attach explicit freshness context to market context, next-ticket radar, and A-share evidence radar packets when they have producer-owned `trade_date/data_date` fields. The context carries global `expected_trade_date`, producer `data_date`, `freshness_state`, and no-provider/no-model/no-trade flags, but it does not use `generated_at/updated_at` as a market data date and does not claim provider-backed acceptance.
- Data Health now exposes `current_evidence_producer_cache_refresh_readiness`, a read-only contract that compares current producer coverage with the local generation contract. It can show `ready_for_local_cache_refresh` or `current_cache_already_has_producer_freshness_context`, but it writes no cache, creates no task, builds no missing packet, refreshes no provider, calls no Tushare/DeepSeek/GitHub service, and cannot clear provider-backed `trade_cal` acceptance.
- Data Health now provides a button-gated `POST /api/data-health/producer-cache-refresh-execution-request` task that creates a local execution-request ticket for the future producer cache refresh task. It binds the current `current_evidence_producer_cache_refresh_readiness.readiness_scope_hash_short` and explicit user confirmation, records safe rows and call ledger, but writes no cache, creates no refresh task, executes no local refresh, builds no missing packets, calls no provider/model/GitHub service, and cannot clear provider-backed `trade_cal` acceptance or production freshness completion.
- Data Health cache now surfaces the latest producer cache-refresh execution-request ticket from local task metadata after reload. This is only cache-only continuity replay; it creates no task, writes no cache, calls no provider/model/GitHub service, and cannot replace the future local producer cache refresh task or provider-backed `trade_cal` acceptance.
- Data Health now provides a second button-gated `POST /api/data-health/producer-cache-refresh` task after the execution-request ticket is bound. It consumes the local source snapshot, builds market context / next-ticket radar / A-share evidence producer packets with explicit `expected_trade_date`, `data_date`, and `freshness_state`, writes only three local SQLite packets, and records a receipt visible through GET metadata replay. It does not write snapshot JSON, write Parquet, call Tushare/DeepSeek/GitHub, execute trades, mutate `strategy action`, or complete provider-backed `trade_cal` freshness acceptance.
- `scripts/data_health_freshness_contract.py` now runs in `scripts/push_gate_3_0.sh` to guard LTG-01 contracts against unsafe regressions: local-only boundaries must remain visible, provider-backed acceptance must remain pending until explicit provider validation, and no Data Health contract may imply external calls, real trades, or strategy action mutation. It also validates the `trade_cal` acceptance dry-run ticket states, the bound execution-request ticket, scope mismatch blocking, latest ticket cache replay, no provider/model/GitHub calls, and no token/env-name leakage.
- Data Health now exposes `trade_cal_provider_acceptance_runbook`, a local execution checklist for future provider-backed `trade_cal` long-window acceptance. It fixes the explicit POST task route, safe payload, call-ledger evidence, schema/window/holiday coverage, failure modes, artifact promotion boundary, and current-evidence isolation, while keeping `provider_backed_long_window_acceptance_done=false`.
- Data Health now exposes `trade_cal_provider_acceptance_promotion_audit`, a local snapshot-only evidence promotion audit. It requires prior provider call ledger evidence, safe ledger fields, a 730-day window, schema/local artifact cross-check, open/closed/current coverage, freshness replay, failure-mode evidence, current-evidence boundary recheck, and an explicit promotion marker before `trade_cal` acceptance can move out of pending; the audit itself never calls Tushare.
- Data Health now exposes `freshness_production_blocker_audit`: a local read-only blocker summary across the freshness matrix, long-window replay fixture, local `trade_cal` artifact validation, provider-backed promotion evidence, current-evidence boundary, decision-surface isolation, and producer expected-date coverage.
- Data Health now exposes `freshness_provider_acceptance_readiness_receipt`: a local read-only receipt that tells whether LTG-01 is ready for an explicit POST `trade_cal` provider acceptance task, what evidence is still missing before promotion, and which shortcuts remain forbidden. It keeps `production_freshness_gate_complete=false`.
- Data Health now exposes `freshness_provider_acceptance_activation_receipt`: a local activation checklist for the future explicit `trade_cal` provider acceptance task. It keeps provider task execution, provider call ledger evidence, explicit promotion marker, and production completion pending while confirming GET cache and React render do not call Tushare/DeepSeek/GitHub or mutate action.
- Data Health now provides a button-gated `POST /api/data-health/trade-cal-provider-acceptance-dry-run` task that creates a local `trade_cal` provider-acceptance scope ticket. It records explicit approval, `trade_cal`-only scope, 730-day window intent, safe credential-presence booleans, a SHA-256 scope hash over non-secret fields, required future evidence, and no-provider/no-model/no-trade/no-action boundaries.
- Data Health cache now surfaces the latest local `trade_cal` provider acceptance dry-run task receipt from task metadata after reload. This is a read-only local lookup that creates no task, calls no provider/model/GitHub service, and still keeps provider-backed acceptance and production freshness completion pending.
- Data Health now provides a button-gated `POST /api/data-health/trade-cal-provider-acceptance-execution-request` task that creates a local execution-request ticket after a dry-run scope hash exists. It binds the requested scope hash to the latest dry-run hash, verifies explicit user confirmation, shows next-execution recipe readiness, and keeps `creates_provider_task=false`, `provider_task_executed_by_request=false`, `provider_execution_implemented=false`, `provider_backed_long_window_acceptance_done=false`, and `production_freshness_gate_complete=false`.
- Data Health cache now surfaces the latest local execution-request ticket from task metadata after reload. This is only a read-only continuity view; it creates no task, calls no provider/model/GitHub service, and cannot replace the future `POST /api/tasks/refresh-tushare-facts` provider task or its call ledger.
- Data Health now provides a button-gated `POST /api/data-health/trade-cal-provider-acceptance-promotion-review` task that saves a local promotion-review receipt after prior evidence has been audited. It records the current promotion audit status, latest execution-request lineage, provider evidence gaps, blocking phases, allowed next step, and no-provider/no-model/no-GitHub/no-trade/no-action boundaries. It creates no provider task, calls no Tushare, writes no Parquet, and keeps `provider_backed_long_window_acceptance_done=false` and `production_freshness_gate_complete=false`.
- Data Health cache now surfaces the latest local promotion-review receipt from task metadata after reload. This is only a read-only continuity view; it creates no task, calls no provider/model/GitHub service, and cannot turn a dry-run, execution-request, local artifact, fixture, or partial call-ledger evidence into provider-backed acceptance.
- Tushare refresh task call-ledger rows can now record explicit `acceptance_mode=provider_backed_trade_cal_long_window` evidence for future provider-backed `trade_cal` acceptance: 730-day window, `cal_date/is_open` schema, open/closed row counts, latest completed trading day, freshness replay evidence, failure-mode evidence, and no-trade/no-action boundaries. This is still button-gated POST evidence, not GET cache execution.
- Data Health can now read the persisted local `command_center_tushare_refresh_packet` from SQLite as prior `trade_cal` acceptance evidence. The lookup is cache-only/read-only, does not create tasks, does not call Tushare, and still requires the promotion audit plus local artifact/current-evidence checks before readiness can clear.
- `scripts/data_health_freshness_contract.py` now exposes `freshness_production_stage_scope_manifest`: a local push-gate manifest for the remaining freshness production stages. It tracks acceptance-matrix boundary, synthetic replay, local `trade_cal` artifact validation, explicit provider `trade_cal` long-window task, safe provider call ledger, provider-backed freshness replay, provider-backed failure modes, producer expected-date coverage, decision-surface isolation, and promotion/release review while keeping `production_freshness_gate_complete=false`.
- Data Health now exposes `freshness_durable_evidence_recipe` and rows: a local LTG-01 durable evidence checklist that ties the remaining production proof to provider `trade_cal` task execution, safe provider call ledger, provider-backed freshness replay, provider failure-mode evidence, producer expected-date coverage, decision-surface isolation, and promotion review. It is cache-only and keeps `provider_backed_trade_cal_acceptance_done=false`, `production_freshness_gate_complete=false`, and `provider_execution_implemented=false`.
- Migration Status now observes the LTG-01 `freshness_production_stage_scope_manifest` from the local static Data Health freshness contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show local matrix/synthetic/local-artifact evidence, expected-date producer coverage, decision-surface isolation, and the remaining provider `trade_cal` long-window, safe call-ledger, provider replay/failure-mode, and promotion blockers without calling Tushare, creating provider tasks, mutating scores/actions, or completing production freshness.

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
- The `trade_cal` provider acceptance dry-run ticket is not provider execution. It only binds the future user-approved real `trade_cal` acceptance scope to safe fields and a hash; it cannot write Parquet, call Tushare, prove `trade_cal` data freshness, or complete LTG-01.
- The latest dry-run receipt visible in GET cache is not a new dry-run and not a provider run. It is only local task metadata replay for audit continuity after refresh.
- The `trade_cal` provider acceptance execution-request ticket is not provider execution. It only checks that a human-approved request is bound to the latest dry-run scope hash and that local blockers are visible; it cannot call Tushare, create the provider task, write Parquet, prove call-ledger evidence, or complete LTG-01/LTG-02.
- The latest execution-request receipt visible in GET cache is not a new request and not a provider run. It is only local task metadata replay; scope-hash match or request readiness is still not provider-backed acceptance.
- The `trade_cal` provider acceptance promotion-review receipt is not provider execution and not production completion. It only records whether prior provider evidence is ready for a later release review; it cannot create provider tasks, call Tushare, promote dry-run/execution-request/local artifact evidence, write Parquet, or mark `production_freshness_gate_complete=true`.
- The latest promotion-review receipt visible in GET cache is not a new review and not a provider run. It is only local task metadata replay; even a release-ready review still needs full gate output and user release confirmation before any production wording can change.
- A `trade_cal` call-ledger row with `acceptance_mode=provider_backed_trade_cal_long_window` is not enough by itself. It only becomes provider-backed long-window evidence when the explicit task also records successful provider rows, 730-day schema/window checks, freshness replay evidence, and failure-mode evidence.
- Reading the persisted Tushare refresh packet in Data Health is not provider execution. It only lets the cache audit discover prior POST task evidence from SQLite; stale, partial, matrix-only, or non-`trade_cal` rows cannot be promoted by the lookup alone.
- The production stage-scope manifest is a local pending checklist. It does not execute provider `trade_cal`, prove call-ledger rows, prove 730-day provider freshness replay, validate provider failure modes, complete producer coverage, mutate decision surfaces, or promote the release.
- The durable evidence recipe is not provider execution or production completion. It only makes the direct evidence bundle explicit; it cannot turn a dry-run ticket, synthetic replay, local artifact, or cache/render path into provider-backed acceptance.
- Global `data_freshness` canonicalization is not provider-backed acceptance. It only normalizes already-present local cache fields for audit readability; visible producers still need explicit expected-date coverage before the producer-coverage blocker can clear.
- Producer freshness context attachment is not provider-backed acceptance. It only makes future local snapshot packets carry their own date contract when explicit producer data dates exist; missing producer data dates must remain blocked or research-only.
- Data Health now exposes `current_evidence_producer_generation_contract`: a local in-memory home-snapshot builder contract for market context, candidate radar, and A-share evidence radar producer freshness fields. It writes no cache, calls no provider/model/GitHub service, keeps `current_cache_refresh_pending=true`, and is not provider-backed `trade_cal` acceptance.
- `current_evidence_producer_cache_refresh_readiness` is not cache refresh execution. It only says whether the local builder can carry producer freshness fields into a future cache refresh or whether the current cache already has those fields; it must keep provider-backed acceptance, production freshness, provider calls, task creation, and cache writes disabled.
- The producer cache-refresh execution-request ticket is not cache refresh execution. It only binds readiness hash plus explicit confirmation to the separate local refresh task; it must keep `writes_snapshot_cache=false`, `creates_task=false`, `executes_local_refresh=false`, `builds_missing_packets=false`, provider/model/GitHub calls false, provider-backed acceptance false, and production freshness false.
- The producer cache-refresh task is local cache continuity, not provider-backed acceptance. Even when it writes the three expected SQLite producer packets and clears the local missing-producer context in GET metadata, it must keep `writes_snapshot_cache=false`, `writes_parquet=false`, `provider_execution_implemented=false`, `provider_backed_trade_cal_acceptance_done=false`, and `production_freshness_gate_complete=false`.
- `freshness_durable_evidence_recipe` now carries the producer generation status into the `current_evidence_producer_coverage` row as `producer_generation_ready_current_cache_refresh_pending` until the local SQLite refresh task runs. This makes the local builder readiness visible while keeping provider-backed `trade_cal` acceptance, provider replay/failure-mode evidence, decision-surface review, and production promotion as blockers.

### Implementation Phases

1. Load and validate a long-window `trade_cal` dataset through the task/storage pipeline.
2. Add expected trade date checks to all current evidence producers.
3. Treat historical sample rows as research-only unless they explicitly match current evidence requirements.
4. Extend tests for holiday clusters, long weekends, missing calendar rows, and provider delay windows.
5. Use the local SQLite producer cache refresh task only after a bound execution-request ticket; treat its receipt as local continuity evidence, not provider acceptance.
6. Keep `freshness_production_stage_scope_manifest` current whenever provider acceptance, producer coverage, decision-surface isolation, or promotion evidence changes.
7. Keep `freshness_durable_evidence_recipe` current whenever direct provider call-ledger, replay, failure-mode, producer, decision-surface, or promotion evidence changes.

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
- Data Health shows `current_evidence_producer_generation_contract` and rows: local home-snapshot builder samples for candidate radar, A-share evidence radar, and market context can attach expected-date/data-date/freshness fields from explicit producer trade dates, while `current_cache_refresh_pending=true`, `writes_snapshot_cache=false`, and provider-backed acceptance remains false.
- Data Health shows `current_evidence_producer_cache_refresh_readiness` and rows: candidate radar, A-share evidence radar, and market context are either ready for a future local cache refresh or already have current-cache producer freshness context; every row keeps `writes_snapshot_cache=false`, `creates_task=false`, `builds_missing_packets=false`, `does_not_refresh_provider=true`, provider-backed acceptance false, and no Tushare/DeepSeek/GitHub/trading side effects.
- `freshness_durable_evidence_recipe.rows[current_evidence_producer_coverage]` shows producer generation readiness separately from production coverage: `producer_generation_contract_ready=true`, `producer_generation_current_cache_refresh_pending=true`, `producer_generation_writes_snapshot_cache=false`, `producer_generation_calls_provider=false`, and `producer_generation_ready_is_not_completion=true`.
- Push gate runs `scripts/data_health_freshness_contract.py` and fails if Data Health contracts lose local-only/no-provider/no-trade/no-action boundaries or falsely claim provider-backed freshness completion.
- Data Health shows `trade_cal_provider_acceptance_runbook` and rows: explicit POST task requirement, safe payload, call ledger, long-window sample, schema, local artifact cross-check, freshness replay, failure modes, artifact promotion, current-evidence boundary, and secret/trade boundary.
- Data Health shows `trade_cal_provider_acceptance_promotion_audit` and rows: explicit prior provider call ledger, safe call-ledger fields, minimum long-window evidence, schema/local artifact cross-check, open/closed/current coverage, freshness replay evidence, failure-mode evidence, current-evidence boundary recheck, explicit promotion marker, and read-only no-provider-call boundary.
- Data Health shows `local_tushare_refresh_packet_summary` when a local Tushare refresh packet exists: source cache, selected APIs, call-ledger counts, `trade_cal` evidence row count, no-provider lookup flags, and non-completion flags.
- Data Health shows `freshness_production_blocker_audit` and rows: every production phase is marked passed, pending, or blocked, with provider-backed `trade_cal`, local artifact, current-evidence, decision-surface, and producer expected-date blockers visible.
- Data Health shows `freshness_provider_acceptance_readiness_receipt` and rows: explicit POST route readiness, cache/render no-provider boundary, current-evidence boundary, decision-surface isolation, producer expected-date coverage, provider evidence ticket, and production-completion boundary.
- Data Health shows `freshness_provider_acceptance_activation_receipt` and rows: readiness receipt visibility, explicit POST task requirement, provider execution evidence required, promotion review required, current-evidence boundary, decision-surface isolation, producer expected-date coverage, fixture/artifact not acceptance, cache/render no-provider boundary, production-completion boundary, and no-trade/no-action boundary.
- Data Health can create a local `trade_cal` provider acceptance dry-run ticket through button-gated `POST /api/data-health/trade-cal-provider-acceptance-dry-run`: selected APIs stay limited to `trade_cal`, ignored APIs remain visible, the scope hash excludes credential material, credential presence is exposed only as booleans/safe labels, and the receipt keeps real provider execution and production promotion blocked.
- Data Health shows `trade_cal_provider_acceptance_next_execution_recipe` and rows: local runbook readiness, readiness receipt, activation receipt, dry-run scope ticket, target POST route, future provider call ledger, freshness replay, failure modes, promotion review, and cache/render/trade boundaries are visible before any real provider acceptance run.
- Data Health can create a local `trade_cal` provider acceptance execution-request ticket through button-gated `POST /api/data-health/trade-cal-provider-acceptance-execution-request`: the requested scope hash must match the latest dry-run hash, explicit confirmation is required, the target route remains `POST /api/tasks/refresh-tushare-facts`, and the receipt keeps `ready_to_execute_from_cache=false`, `creates_provider_task=false`, provider execution, provider-backed acceptance, and production freshness completion blocked.
- Data Health shows the latest execution-request ticket in cache as metadata only; cache lookup must keep `cache_get_creates_task=false`, `cache_get_external_calls=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, no secrets, no trades, and no `strategy action` mutation.
- Local `trade_cal` Parquet validation can pass without setting provider-backed acceptance to done.
- `freshness_production_stage_scope_manifest` contains every required production stage and each row keeps `provider_backed_trade_cal_acceptance_done=false`, `production_freshness_gate_complete=false`, `real_trade_cal_long_window_validation_done=false`, `provider_refresh_called_by_contract=false`, `provider_execution_implemented=false`, `provider_call_ledger_evidence_done=false`, `freshness_replay_provider_evidence_done=false`, `failure_mode_provider_evidence_done=false`, `current_evidence_producer_coverage_complete=false`, `decision_surface_mutated_by_contract=false`, no cache/render external calls, no provider/model/GitHub calls, no trades, no `strategy action` mutation, and no secrets.
- Data Health shows `freshness_durable_evidence_recipe` and ten rows for local freshness matrix regression, local `trade_cal` artifact validation, provider scope ticket, explicit provider `trade_cal` task, safe provider call ledger, provider freshness replay, provider failure-mode evidence, current-evidence producer coverage, decision-surface isolation, and production promotion review.
- `freshness_durable_evidence_recipe` keeps `durable_evidence_complete=false`, `durable_promotion_ready=false`, `provider_backed_trade_cal_acceptance_done=false`, `production_freshness_gate_complete=false`, `real_trade_cal_long_window_validation_done=false`, `provider_execution_implemented=false`, and `provider_refresh_called_by_recipe=false` until direct provider-backed evidence is attached.
- Push gate fails if `freshness_durable_evidence_recipe` loses its cache-only/no-provider/no-task/no-trade/no-action/no-secret boundaries or if it claims production completion from local contracts.

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
- Do not treat `trade_cal_provider_acceptance_dry_run_receipt.status=trade_cal_acceptance_dry_run_ready_real_execution_still_blocked` as a real Tushare run, provider-backed acceptance, Parquet write, or production freshness completion.
- Do not treat `trade_cal_provider_acceptance_next_execution_recipe.recipe_ready_for_user_confirmation=true` as a real Tushare run, provider-backed acceptance, Parquet write, or production freshness completion; it only means the next explicit provider task has enough local scope evidence for user confirmation.
- Do not treat `freshness_durable_evidence_recipe.local_recipe_ready=true` as provider-backed acceptance, provider task execution, durable promotion, or production freshness completion.
- Do not treat the durable evidence recipe as permission to call Tushare from GET cache or React render.
- Do not treat `current_evidence_decision_surface_audit` as runtime rescore, packet filtering, or provider-backed freshness proof.
- Do not treat `current_evidence_producer_coverage_audit` as building missing packets, refreshing providers, or proving full producer coverage when rows are `not_observed`.
- Do not treat `current_evidence_producer_generation_contract.local_generation_contract_ready=true` as a cache refresh, provider-backed `trade_cal` run, producer coverage completion, or production freshness completion.
- Do not treat `freshness_durable_evidence_recipe.rows[current_evidence_producer_coverage].current_status=producer_generation_ready_current_cache_refresh_pending` as a blocker clear. It means the next local cache refresh and direct provider evidence are still pending.
- Do not treat `scripts/data_health_freshness_contract.py` passing as real `trade_cal` provider acceptance; it only blocks local contract regressions.
- Do not treat `freshness_production_stage_scope_manifest` as provider execution, provider call-ledger evidence, freshness replay evidence, failure-mode evidence, producer coverage completion, decision-surface mutation, promotion approval, or production freshness completion.

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
- Tushare refresh packets now expose `provider_target_sample_execution_recipe`: a local ordered recipe for the future explicit target-sample provider validation step. It pins manual confirmation, scope/payload review, POST task execution, safe provider call-ledger capture, sample row review, failure-mode review, promotion audit, and storage/cache promotion review while keeping provider task creation by the recipe, provider execution by the recipe, full-interface acceptance, and `production_tushare_pipeline_complete` false.
- `POST /api/tasks/tushare-provider-target-sample-execution-request` now creates a local scope-bound execution-request ticket for the future target-sample provider validation step. It requires explicit operator confirmation and the latest `provider_target_sample_execution_recipe.execution_recipe_scope_hash`, rejects mismatched hashes, records the future `POST /api/tasks/refresh-tushare-facts` target payload, and keeps `creates_provider_task=false`, `provider_task_executed_by_request=false`, `provider_execution_implemented=false`, `provider_backed_target_sample_acceptance_done=false`, `full_interface_acceptance_done=false`, and `production_tushare_pipeline_complete=false`.
- Data Health cache now surfaces the latest local Tushare target-sample execution-request ticket from task metadata after reload. This is only a read-only continuity view for LTG-02 scope, target APIs, blockers, and no-provider boundaries; it creates no task, calls no Tushare/DeepSeek/GitHub service, and cannot replace the future `POST /api/tasks/refresh-tushare-facts` provider task or its call ledger.
- React Data Health now renders the latest Tushare target-sample execution-request metadata, target route, requested target groups, selected APIs, scope-hash match, operator confirmation, provider-pending flags, cache/render no-external flags, and raw sanitized receipt/rows. This is a display-only cache surface; it adds no trigger button and cannot run Tushare, DeepSeek, GitHub, worker, or trading paths.
- `scripts/tushare_acceptance_contract.py` now also emits `interface_group_scope_rows`, a local scope manifest for all seven LTG-02 target groups: `trade_calendar`, margin, dragon-tiger, limit/emotion, chip distribution, financial disclosure, and hard-risk. Each row pins the required POST route and acceptance layer while keeping real provider sample evidence, promotion review, full-interface acceptance, and production completion pending.
- `scripts/tushare_acceptance_contract.py` is now part of the local push gate. It exercises only local matrix/readiness contract helpers and prevents matrix-only rows, failure-mode QA, request-parameter QA, target-sample plans, or provider-readiness audits from being mistaken for provider-backed production acceptance.
- `POST /api/tasks/refresh-tushare-facts` now exposes an explicit `provider_backed_trade_cal_long_window` call-ledger evidence mode for future `trade_cal` provider acceptance. It does not run by default, does not make `trade_cal` full-interface acceptance, and still requires replay/failure-mode evidence before provider-backed long-window acceptance can be marked on the ledger row.
- Data Health now adds a separate local `trade_cal` execution-request ticket before the real `refresh-tushare-facts` provider task. It binds the latest dry-run scope hash to a user-confirmed request, rejects mismatched hashes, and keeps `creates_provider_task=false`, `provider_execution_implemented=false`, `provider_backed_long_window_acceptance_done=false`, and `production_tushare_pipeline_complete=false`.
- `scripts/tushare_acceptance_contract.py` now emits `tushare_production_stage_scope_manifest`: a local push-gate manifest for the remaining full pipeline stages. It tracks POST/mode gate, core light revalidation, `trade_cal`, margin, dragon-tiger, limit/emotion, chip distribution, financial disclosure, hard-risk, and full-interface promotion/storage review while keeping `production_tushare_pipeline_complete=false`.
- Tushare refresh packets now expose `tushare_durable_evidence_recipe` and rows: a local LTG-02 durable evidence checklist for core light revalidation, seven provider target-sample domains, safe provider call ledger, failure-mode/parameter review, full-interface promotion review, and storage/cache promotion review. It keeps `provider_backed_acceptance_done=false`, `full_interface_acceptance_done=false`, `production_tushare_pipeline_complete=false`, and cache/render provider-call flags false.
- Migration Status now observes the LTG-02 `tushare_production_stage_scope_manifest` from the local static Tushare acceptance contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the ten remaining Tushare production stages, local light-path evidence, and provider sample/promotion/storage blockers without calling Tushare, creating provider tasks, writing Parquet, mutating scores/actions, or completing the production Tushare pipeline.

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
- `provider_target_sample_execution_request_receipt.local_execution_request_ready=true` only means operator approval and the latest recipe scope are bound to a future target-sample provider task request. It does not create the provider task, call Tushare, write Parquet, prove call-ledger evidence, promote target-sample acceptance, or complete LTG-02.
- The latest Tushare target-sample execution-request receipt visible in Data Health GET cache is not a new request and not a provider run. It is only local task metadata replay for audit continuity; scope-hash match or request readiness is still not provider-backed target-sample acceptance.
- The local Tushare acceptance push-gate contract is not a provider run; it only blocks regressions in button gating, matrix semantics, call-ledger requirements, pending provider acceptance flags, and no-trade/no-action boundaries.
- `interface_group_scope_rows` is a scope manifest only. It proves the acceptance plan names every target group, not that real Tushare samples, provider promotion, full-interface acceptance, or production completion have happened.
- The `provider_backed_trade_cal_long_window` task mode is a controlled evidence marker for the `trade_cal` target only. It is not Tushare full-interface acceptance, not production pipeline completion, and not automatic provider execution.
- The Data Health `trade_cal` execution-request ticket is a local pre-provider request layer only. It does not execute `refresh-tushare-facts`, does not call Tushare, does not create provider rows, does not validate any extended interface, and cannot complete the Tushare production pipeline.
- `GET /api/bootstrap/status` now exposes safe runtime mode visibility, config rows, and `live_light` policy; `POST /api/bootstrap/live-startup` now creates a local-only task skeleton with task catalog coverage, rate limiting, one-task-per-window dedupe/reuse, safe failure display, and token-safe call ledger. Command Center Home can create that local skeleton once per browser session after initial cache render only in `live_light` mode with sources enabled. Provider execution is still pending: the skeleton does not refresh Tushare, does not call DeepSeek, and does not start worker orchestration.
- The production stage-scope manifest is a local pending checklist. It does not execute Tushare, prove provider call-ledger rows, prove non-empty samples, validate provider failure modes, complete full-interface selection, promote storage/artifacts, or mark production Tushare complete.
- The Tushare durable evidence recipe is not provider execution or production completion. It only names the direct evidence bundle still required; it cannot turn target-sample execution recipes, local/fake samples, matrix rows, failure-mode QA, or request-parameter QA into provider-backed full-interface acceptance.

### Implementation Phases

1. Validate `trade_cal` first because freshness depends on it.
2. Bind every real `trade_cal` provider acceptance attempt to a prior dry-run scope hash and execution-request ticket before `POST /api/tasks/refresh-tushare-facts` is allowed for acceptance evidence.
3. Validate market evidence groups one at a time: margin, dragon-tiger, limit/emotion, chip, disclosure, hard risk.
4. Add per-interface request parameter contracts and safe error states.
5. Persist only production-approved datasets; keep other results as validation records until storage contracts are ready.
6. Add a future `live_light` bootstrap task that can refresh only current target / holdings / watchlist light data through POST task, with `daily`, `daily_basic`, `moneyflow`, and `trade_cal if needed` as the initial allowed interface set.
7. Add staged `live_light` interface switches for margin, limit/emotion, chip, dragon-tiger, disclosure, and hard-risk evidence; keep them opt-in and separate from the default light set.
8. Define an intraday-provider adapter contract before any realtime market-state panel uses non-Tushare data.
9. Keep `tushare_production_stage_scope_manifest` current whenever provider samples, promotion review, storage promotion, or runtime mode evidence changes.
10. Keep `tushare_durable_evidence_recipe` current whenever provider call-ledger evidence, target-domain sample evidence, failure-mode evidence, full-interface promotion, or storage/cache promotion state changes.

### Acceptance Criteria

- Every selected interface runs through POST task pipeline only.
- `trade_cal` provider acceptance uses the local dry-run scope ticket plus execution-request ticket as pre-provider gates; neither ticket may be counted as provider execution or full-interface acceptance.
- `cache_only` GET cache and React render never call Tushare directly.
- Future `live_light` refresh can only be created by a POST bootstrap task after initial cache render, with rate limit, dedupe, symbol limit, and visible mode state.
- Future `live_light` defaults to current target / current holdings / watchlist and defaults to at most 20 symbols.
- `trade_cal if needed`, `daily`, `daily_basic`, and `moneyflow` are the only default light-refresh APIs; staged APIs require explicit payload/config.
- Every interface records `call_ledger`, `row_count`, `data_date`, `local_fetched_at`, `call_status`, and `error_message_safe`.
- Permission denied, no record, empty window, parse failure, missing parameter, and blocked state are distinguishable.
- `no_record` is treated as an evidence state, not as negative market evidence or a failed validation by itself.
- Any non-Tushare intraday adapter must expose provider identity, freshness, call ledger, mode gate, and safe-error status before UI display.
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
- Data Health shows the latest Tushare target-sample execution-request ticket in cache as metadata only; cache lookup must keep `cache_get_creates_task=false`, `cache_get_external_calls=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, no secrets, no trades, and no `strategy action` mutation.
- Local push-gate output includes `interface_group_scope_rows` for all seven target groups, with every row still reporting `real_provider_sample_still_required=true`, `provider_backed_acceptance_done=false`, `full_interface_acceptance_done=false`, and `production_tushare_pipeline_complete=false`.
- `provider_acceptance_readiness_audit.provider_backed_acceptance_done=false` and `production_tushare_pipeline_complete=false` until real provider-backed full-interface acceptance is explicitly proven.
- `scripts/tushare_acceptance_contract.py` passes in the push gate while still reporting `provider_backed_acceptance_done=false`, `production_tushare_pipeline_complete=false`, and `full_interface_acceptance_done=false`.
- `tushare_production_stage_scope_manifest` contains every required production stage and each row keeps `provider_backed_acceptance_done=false`, `production_tushare_pipeline_complete=false`, `full_interface_acceptance_done=false`, `real_provider_sample_still_required=true`, `provider_promotion_still_required=true`, `provider_execution_implemented=false`, `provider_call_ledger_evidence_done=false`, `full_interface_selection_done=false`, `failure_mode_evidence_done=false`, `request_parameter_provider_window_done=false`, `parquet_promotion_done=false`, no cache/render external calls, no provider/model/GitHub calls, no trades, no `strategy action` mutation, and no secrets.
- Tushare refresh packets expose `tushare_durable_evidence_recipe` with all required evidence keys, positive blocker count, `durable_evidence_complete=false`, `durable_promotion_ready=false`, `provider_execution_implemented_by_recipe=false`, `provider_refresh_called_by_recipe=false`, `provider_call_ledger_evidence_done=false`, `failure_mode_evidence_done=false`, `request_parameter_provider_window_done=false`, `parquet_promotion_done=false`, no cache/render external calls, no provider/model/GitHub calls, no trades, no `strategy action` mutation, and no secrets.
- Push gate fails if `tushare_durable_evidence_recipe` loses its local-only/no-provider/no-task/no-trade/no-action/no-secret boundaries or if it claims provider-backed full-interface acceptance from local contracts.
- Tokens are never printed, stored in packets, or exposed to frontend.
- `trade_cal` provider-backed long-window evidence requires explicit payload, long-window schema evidence, freshness replay, and failure-mode validation; a plain successful `trade_cal` refresh remains a normal selected API result.
- Live startup UI shows current mode, Tushare auto-refresh on/off, latest bootstrap task status, skipped-by-rate-limit/session state, and safe errors without exposing token/key.
- Settings / Config Health shows current runtime mode and the `live_light` config contract through `GET /api/bootstrap/status`; Command Center Home can request the local skeleton after cache render when `live_light` is explicitly enabled.

### Forbidden

- Do not call Tushare from GET cache or page render.
- Do not treat the React mounted POST bootstrap skeleton as a direct render/provider call; keep the distinction explicit in tests and docs.
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
- Do not treat the latest Tushare target-sample execution-request cache replay as provider execution, provider call-ledger evidence, target-sample acceptance, full-interface acceptance, or production Tushare completion.
- Do not treat `scripts/tushare_acceptance_contract.py` passing as real Tushare provider acceptance; it is only a local push-gate regression guard.
- Do not treat `tushare_production_stage_scope_manifest` as provider execution, provider call-ledger evidence, non-empty sample evidence, failure-mode evidence, full-interface selection, storage/artifact promotion, or production Tushare completion.
- Do not treat `tushare_durable_evidence_recipe.local_recipe_ready=true` as provider-backed acceptance, provider task execution, durable promotion, storage promotion, or production Tushare completion.
- Do not call Tushare from GET cache or React render because a durable recipe exists.
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
- `POST /api/factor-quant/provider-small-pool-dry-run` now creates a button-gated local scope ticket for future provider-backed Factor Test small-pool validation. It validates explicit user approval, bounded A-share symbols, sample window length, required metrics, dataset scope, and server-side Tushare credential presence as booleans only, then writes `provider_small_pool_acceptance_dry_run_receipt` and rows into the Factor Quant Hub cache. This is a dry-run ticket only: it does not call Tushare, call DeepSeek, compute production IC, enter evidence/next-session projection, mutate `strategy action`, execute trades, or expose token/key values or env key names.
- Factor Test Lab packets now expose `provider_small_pool_execution_recipe`: a local ordered execution recipe for the future explicit provider-backed small-pool validation task. It fixes scope ticket review, explicit provider task creation, safe provider call-ledger capture, sample row collection, multi-horizon forward returns, rolling IC/Rank IC/ICIR, cost/turnover, neutralization stability, PIT/lookahead/survivorship controls, and promotion review while keeping `provider_task_created=false`, `provider_execution_implemented=false`, `provider_call_ledger_evidence_done=false`, `provider_backed_small_pool_validation_done=false`, and `production_factor_test_validation_complete=false`.
- `POST /api/factor-quant/provider-small-pool-execution-request` now creates a button-gated local execution-request ticket for future provider-backed Factor Test small-pool validation. It binds the latest dry-run scope hash, explicit user confirmation, symbols, date window, metrics, horizons, target provider route, and execution recipe status while keeping `provider_task_created=false`, `provider_execution_implemented=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, `contains_secret=false`, and `production_factor_test_validation_complete=false`.
- React Factor Quant Hub now promotes the provider small-pool execution-request ticket status and blocker count into the top metric grid, while the detailed table remains read-only. This is a visibility guard for LTG-03; it does not create a provider task, call Tushare/DeepSeek/GitHub, compute production metrics, or mark provider-backed validation complete.
- Factor Test Lab packets now expose `durable_evidence_recipe` and `durable_evidence_rows`: a local LTG-03 durable evidence checklist that ties the visible light metric baseline, storage/query boundary, local dataset sample evidence, production QA, provider blocker audit, readiness/activation receipts, dry-run scope ticket, execution recipe, and execution-request ticket to the still-missing direct provider evidence for task id, safe call ledger, sample rows, multi-horizon returns, rolling IC/Rank IC/ICIR, cost/turnover, neutralization stability, PIT/lookahead/survivorship controls, full-market boundary review, and promotion review. It keeps `durable_evidence_complete=false`, `provider_execution_implemented=false`, `provider_backed_small_pool_validation_done=false`, `full_market_validation_done=false`, and `production_factor_test_validation_complete=false`.
- `scripts/factor_test_lab_contract.py` is now part of the local push gate. It uses synthetic local light observations and cache-only service contracts to keep Factor Test Lab metrics, small-pool readiness, storage-query consumption, production QA, provider activation, provider small-pool dry-run scope tickets, and execution-request tickets clearly separated from provider-backed / full-market validation.
- The same contract now emits `factor_metric_scope_rows` for `ic`, `rank_ic`, `icir`, `group_return`, `top_bottom`, `max_drawdown`, `neutral_ic`, `out_of_sample_decay`, and `cost_model`. Each row is a research-only production-scope manifest: selected by the dry-run scope, required before production, not provider-backed validation, not full-market validation, not production completion, not evidence/action mutation, and not an external call.
- The same contract now emits `factor_test_production_stage_scope_manifest`: a local push-gate manifest for the remaining production validation stages. It tracks local light baseline, provider small-pool scope ticket, provider-backed small-pool sample, multi-horizon returns, rolling IC/ICIR, cost/turnover, neutralization stability, PIT/lookahead/survivorship controls, full-market boundary review, and promotion review while keeping `production_factor_test_validation_complete=false`.
- Migration Status now observes the LTG-03 `factor_test_production_stage_scope_manifest` from the local static Factor Test Lab contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the ten remaining Factor Test Lab production-validation stages, local light/scope-ticket evidence, and provider sample / rolling-window / cost / neutralization / bias / full-market / promotion blockers without calling Tushare, creating provider tasks, computing production metrics, mutating scores/actions, or completing production Factor Test validation.

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
- The provider small-pool dry-run ticket is not provider execution. Even when the local preflight is ready, it reports `ready_to_execute_real_task=false`, keeps `provider_execution_implemented=false`, and requires a separate explicit provider-backed validation task bound to the safe scope hash before any real small-pool evidence can be accepted.
- The `provider_small_pool_execution_recipe` is not provider execution. It only orders the future provider-backed validation evidence sequence and still requires an explicit provider task, safe call ledger rows, non-empty samples, multi-horizon forward returns, rolling IC/ICIR, cost/turnover validation, neutralization stability, PIT/bias controls, and manual promotion review.
- The `provider_small_pool_execution_request_receipt` is not provider execution. It only binds the latest dry-run scope hash and future provider task target; it cannot create the provider task, call Tushare, compute production metrics, collect provider rows, or mark provider-backed validation complete.
- The Factor Test durable evidence recipe is not provider execution or production completion. It only makes the direct evidence bundle explicit; it cannot turn light metrics, storage rows, local dataset samples, blocker audits, dry-run scope tickets, execution recipes, or execution-request tickets into provider-backed small-pool validation.
- The `factor_metric_scope_rows` manifest fixes the required metric list and research-only boundaries, but it is still a local contract. It does not create provider-backed sample rows, safe provider call-ledger evidence, multi-horizon forward-return labels, or production promotion evidence.
- The production stage-scope manifest is a local pending checklist. It does not execute providers, prove safe provider call-ledger rows, prove non-empty target samples, validate multi-horizon/rolling/cost/neutralization/bias evidence, promote full-market proof, or mark production Factor Test validation complete.
- The local Factor Test Lab push-gate contract is not a provider run; it only blocks regressions where local light metrics, storage query rows, or QA checklist rows are mistaken for production validation.

### Implementation Phases

1. Stabilize single-factor research metrics on small real pools.
2. Add multiple forward-return horizons and rolling windows.
3. Add production cost assumptions and turnover diagnostics.
4. Add factor state transitions: `research_pass`, `watchlist`, `disabled`, `invalid`, `not_enough_data`.
5. Generate provider small-pool dry-run scope tickets before any real provider-backed validation run.
6. Keep `provider_small_pool_execution_recipe` current so future provider-backed validation has a fixed execution order before implementation.
7. Generate a scope-bound `provider_small_pool_execution_request_receipt` before any future provider-backed validation task is submitted.
8. Keep `factor_tests.durable_evidence_recipe` current whenever provider task evidence, call-ledger evidence, metric validation, full-market boundary review, or promotion evidence changes.
9. Keep `production_validation_qa_contract` current until provider-backed validation tasks can prove completion.
10. Keep `factor_test_production_stage_scope_manifest` current whenever provider samples, rolling windows, cost assumptions, neutralization evidence, bias controls, or promotion evidence changes.

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
- `provider_small_pool_acceptance_dry_run_receipt` may report `preflight_ready_for_user_approved_real_task=true` only when approval, bounded symbols, window length, required metrics, and server credential presence are all satisfied. It must still report `ready_to_execute_real_task=false`, `provider_execution_implemented=false`, `provider_backed_small_pool_validation_done=false`, `production_factor_test_validation_complete=false`, `cache_get_external_calls=false`, `react_render_external_calls=false`, `tushare_called=false`, `deepseek_called=false`, and `contains_secret=false`.
- `provider_small_pool_execution_recipe.local_recipe_ready=true` only means a safe provider small-pool dry-run scope ticket is visible and the future provider-backed validation sequence can be audited. It must keep every phase pending, keep `provider_task_created=false`, `provider_execution_implemented=false`, `provider_call_ledger_evidence_done=false`, `sample_rows_collected=false`, `multi_horizon_forward_returns_done=false`, `rolling_window_validation_done=false`, `neutralization_stability_done=false`, `provider_backed_small_pool_validation_done=false`, `production_factor_test_validation_complete=false`, `external_calls_triggered=false`, `tushare_called=false`, and `deepseek_called=false`.
- `provider_small_pool_execution_request_receipt.local_execution_request_ready=true` only means the latest dry-run scope hash, user confirmation, and future provider task target are bound. It must keep `provider_task_created=false`, `provider_execution_implemented=false`, `provider_call_ledger_evidence_done=false`, `sample_rows_collected=false`, `provider_backed_small_pool_validation_done=false`, `production_factor_test_validation_complete=false`, `external_calls_triggered=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, and `contains_secret=false`.
- Factor Quant Hub shows `factor_tests.durable_evidence_recipe` and rows with local surface evidence passed, direct provider-backed evidence still blocked, `durable_evidence_complete=false`, `durable_promotion_ready=false`, `provider_execution_implemented=false`, `provider_backed_small_pool_validation_done=false`, `full_market_validation_done=false`, and `production_factor_test_validation_complete=false`.
- Push gate fails if `factor_tests.durable_evidence_recipe` loses its no-provider/no-model/no-trade/no-action/no-secret boundaries, claims completion from local contracts, or allows Tushare/DeepSeek/GitHub calls from GET cache or React render.
- `factor_metric_scope_rows` must list all required production metrics: `ic`, `rank_ic`, `icir`, `group_return`, `top_bottom`, `max_drawdown`, `neutral_ic`, `out_of_sample_decay`, and `cost_model`. Every row must remain research-only with `provider_backed_small_pool_validation_done=false`, `full_market_validation_done=false`, `production_factor_test_validation_complete=false`, no provider/model/GitHub calls, no real trades, and no `strategy action` mutation.
- `factor_test_production_stage_scope_manifest` must list all required production stages: local light baseline, provider small-pool scope ticket, provider-backed small-pool sample, multi-horizon returns, rolling IC/ICIR, cost/turnover, neutralization stability, PIT/lookahead/survivorship controls, full-market boundary review, and promotion review. Every row must keep provider-backed small-pool validation, full-market validation, provider execution, call-ledger evidence, multi-horizon/rolling/cost/neutralization/bias evidence, production completion, cache/render external calls, trades, and `strategy action` mutation false.
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
- Do not treat `provider_small_pool_acceptance_dry_run_receipt` as provider-backed validation, real Tushare sample evidence, IC/Rank IC/ICIR production proof, full-market proof, or permission to expose env key names / credential values.
- Do not treat `provider_small_pool_execution_recipe` as provider task creation, Tushare execution, provider call-ledger evidence, non-empty provider sample rows, IC/Rank IC/ICIR production proof, multi-horizon/rolling/cost/neutralization/bias validation, full-market proof, or production Factor Test completion.
- Do not treat `factor_tests.durable_evidence_recipe.local_recipe_ready=true` as provider execution, durable evidence completion, provider-backed small-pool validation, full-market validation, production promotion, or production Factor Test completion.
- Do not treat the Factor Test durable evidence recipe as permission to call Tushare, DeepSeek, or GitHub from GET cache or React render.
- Do not treat `factor_metric_scope_rows` as real metric evidence; it is a required-metric checklist and research-only boundary manifest before future provider-backed validation.
- Do not treat `factor_test_production_stage_scope_manifest` as provider execution, provider call-ledger evidence, non-empty sample evidence, multi-horizon/rolling/cost/neutralization/bias validation, full-market promotion, or production Factor Test completion.
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
- `POST /api/factor-quant/universe-worker-batch-dry-run` now creates a button-gated local scope ticket for future worker-backed Factor universe research. It validates explicit approval, universe mode, bounded watchlist/custom pool or full-pool resolver scope, required datasets, required stages, and a safe scope hash, then writes `universe_worker_batch_dry_run_receipt` and rows into the Factor Quant Hub cache. This is a dry-run ticket only: it does not create a worker task, start Celery/local workers, call Tushare, call DeepSeek, compute production rank/zscore/neutralization, mutate `strategy action`, execute trades, or expose token/key material.
- Factor Quant Hub now exposes `universe_worker_batch_execution_recipe`: a local ordered execution recipe for the future explicit worker-backed batch research task. It fixes scope ticket review, explicit worker task creation, worker runtime binding, storage read execution, cross-sectional rank, zscore, neutralization, factor-combination execution, result-summary persistence, and production promotion review while keeping `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `large_universe_pipeline_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, and `production_factor_universe_complete=false`.
- `POST /api/factor-quant/universe-worker-batch-execution-request` now creates a button-gated local execution-request ticket for the future worker-backed Factor universe batch research task. It binds the latest dry-run scope hash, explicit user confirmation, universe mode, stage scope, target worker route, and execution recipe status while keeping `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `full_pool_validation_done=false`, `external_calls_triggered=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, and `production_factor_universe_complete=false`.
- `POST /api/factor-quant/universe-worker-batch-research` now creates a button-gated local research receipt. It binds the latest execution-request scope hash and task id, writes `universe_worker_batch_research_receipt` and rows into the Factor Quant Hub cache, and marks only the local receipt / scope lineage ready. It keeps `worker_task_created=false`, `worker_task_executed=false`, `worker_process_started=false`, `worker_started=false`, `redis_pinged=false`, `storage_read_executed=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `external_calls_triggered=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, and `production_factor_universe_complete=false`.
- Factor Quant Hub now exposes `universe_durable_evidence_recipe` and `universe_durable_evidence_rows`: a local LTG-04 durable evidence checklist that ties the visible mode contract, storage read-plan, readiness/activation receipts, local rank/zscore dry-run, worker-batch scope ticket, execution recipe, execution-request ticket, and local research receipt to the still-missing direct worker evidence for runtime binding, durable logs, storage reads, cross-sectional rank, zscore, neutralization, factor-combination output, persisted summary, full-pool validation, and promotion review. It keeps `durable_evidence_complete=false`, `worker_task_created=false`, `worker_task_executed=false`, `large_universe_pipeline_done=false`, `full_pool_validation_done=false`, and `production_factor_universe_complete=false`.
- `scripts/factor_universe_contract.py` is now part of the local push gate. It validates LTG-04 universe modes, local storage read-plan consumption, worker-batch dry-run ticket, execution-request ticket, local research receipt, task catalog button gating, React read-only display, partial-pool-not-full-market-proof visibility, no batch execution, no provider/model/GitHub calls, no trades, and no action mutation while `production_factor_universe_complete=false`.
- The same contract now emits `worker_stage_scope_rows` for `storage_read_plan`, `worker_batch_scope`, `cross_sectional_rank`, `zscore`, `neutralization`, `factor_combination`, `result_summary`, and `promotion_review`. Each row is a pending local stage-scope manifest: selected by the dry-run scope, required before production, not worker execution, not rank/zscore or neutralization completion, not provider/model execution, not full-pool validation, and not production completion.
- Migration Status now observes the LTG-04 `factor_universe_worker_batch_stage_scope_manifest` from the local static Factor universe contract and surfaces it in `ltg_stage_scope_observed_rows`. The next-action queue now requires the local worker-batch research receipt after the execution-request ticket, then leaves worker runtime/storage/metric/promotion evidence as the future production gap. This makes the global 14-LTG page show the eight remaining worker-batch stages and their no-execution boundaries without starting a worker, creating a real worker task, computing rank/zscore, running neutralization, calling providers/models/GitHub, mutating scores/actions, or completing full-pool production research.

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
- The worker-batch dry-run ticket is not worker execution. Even when local preflight is ready, it reports `ready_to_execute_worker_task=false`, keeps `worker_execution_implemented=false`, and requires a separate explicit worker-backed task bound to the safe scope hash before any large-universe evidence can be accepted.
- The `universe_worker_batch_execution_recipe` is not worker execution. It only orders the future evidence sequence and still requires an explicit worker task, durable task logs, storage read execution evidence, rank/zscore output, neutralization output, factor combination evidence, result summary persistence, and manual promotion review.
- The Factor Universe durable evidence recipe is not worker execution or production completion. It only makes the direct evidence bundle explicit; it cannot turn local read plans, readiness receipts, rank/zscore dry-runs, dry-run scope tickets, or execution recipes into worker-backed full-pool research.
- The `worker_stage_scope_rows` manifest fixes the required worker-batch stage list and no-execution boundaries, but it is still a local contract. It does not create durable task logs, large-universe result rows, production rank/zscore, neutralization output, factor-combination research, or promotion evidence.
- The Factor universe push-gate contract is local only; it does not run worker-backed batch research, rank/zscore, neutralization, provider-backed validation, factor combination research, or full-pool production research.

### Implementation Phases

1. Define `watchlist`, `custom_pool`, and `full_pool` universe contracts.
2. Generate worker-batch dry-run scope tickets before any real worker-backed batch execution.
3. Keep `universe_worker_batch_execution_recipe` current so worker-backed research has a fixed execution order before implementation.
4. Keep `universe_durable_evidence_recipe` current whenever task id, worker runtime, storage-read, metric output, result persistence, full-pool validation, or promotion evidence changes.
5. Add batch execution through task pipeline.
6. Add cross-sectional rank, zscore, neutralization, and result summaries.
7. Keep UI as progress/result display only.

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
- `universe_worker_batch_dry_run_receipt.preflight_ready_for_explicit_worker_batch_task=true` only after approval, mode scope, dataset/stage scope, and local read-plan prerequisites are visible. It must still report `ready_to_execute_worker_task=false`, `worker_execution_implemented=false`, `worker_batch_executed=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, `full_pool_validation_done=false`, `production_factor_universe_complete=false`, `external_calls_triggered=false`, `tushare_called=false`, and `deepseek_called=false`.
- `universe_worker_batch_execution_recipe.local_recipe_ready=true` only means a safe worker-batch dry-run scope ticket is visible and the future execution sequence can be audited. Activation/read-plan readiness remains separately visible; the recipe must still keep every phase pending, keep `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, `production_factor_universe_complete=false`, `external_calls_triggered=false`, `tushare_called=false`, and `deepseek_called=false`.
- Factor Quant Hub shows `universe_durable_evidence_recipe` and rows with local surface evidence passed, including the worker-batch execution-request surface, while direct worker/full-pool evidence remains blocked: `durable_evidence_complete=false`, `durable_promotion_ready=false`, `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `storage_read_executed=false`, `cross_sectional_rank_zscore_done=false`, `zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, `result_summary_persisted=false`, `full_pool_validation_done=false`, and `production_factor_universe_complete=false`.
- Push gate fails if `universe_durable_evidence_recipe` loses its no-worker/no-provider/no-model/no-trade/no-action/no-secret boundaries, claims completion from local contracts, or allows Tushare/DeepSeek/GitHub calls from GET cache or React render.
- `worker_stage_scope_rows` must list all required worker stages: `storage_read_plan`, `worker_batch_scope`, `cross_sectional_rank`, `zscore`, `neutralization`, `factor_combination`, `result_summary`, and `promotion_review`. Every row must keep `worker_execution_implemented=false`, `worker_batch_executed=false`, `large_universe_pipeline_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `full_pool_validation_done=false`, `production_factor_universe_complete=false`, no provider/model/GitHub calls, no render-started full-pool work, no frontend rank/zscore, no real trades, and no `strategy action` mutation.
- `scripts/factor_universe_contract.py` passes in the local push gate while reporting `large_universe_pipeline_done=false`, `full_pool_validation_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, and `production_factor_universe_complete=false`.

### Forbidden

- Do not block page render with full-pool computation.
- Do not write universe data to git.
- Do not treat partial universe samples as full-market proof.
- Do not treat `universe_local_rank_zscore_dry_run` as real full-pool research, provider-backed validation, or trading evidence.
- Do not treat `universe_execution_readiness_audit` as production factor-universe completion while it reports execution pending.
- Do not treat `universe_execution_readiness_receipt.ready_for_explicit_worker_batch_task=true` as worker-backed batch execution or full-pool research completion; it only identifies the next explicit task gate.
- Do not treat `universe_execution_activation_receipt.local_activation_receipt_ready=true` as worker-backed batch execution, production rank/zscore, neutralization, provider-backed validation, full-pool completion, or production Factor universe completion.
- Do not treat `universe_worker_batch_dry_run_receipt` as worker-backed execution, durable task logs, large-universe result rows, production rank/zscore, neutralization, factor-combination research, provider-backed validation, full-pool completion, or production Factor universe completion.
- Do not treat `universe_worker_batch_execution_recipe` as worker task creation, worker startup, durable task log evidence, storage read execution evidence, rank/zscore output, neutralization output, factor-combination research, result summary persistence, provider-backed validation, full-pool completion, or production Factor universe completion.
- Do not treat `universe_durable_evidence_recipe.local_recipe_ready=true` as worker execution, durable evidence completion, full-pool validation, production promotion, provider/model evidence, or production Factor universe completion.
- Do not treat the Factor Universe durable evidence recipe as permission to call Tushare, DeepSeek, or GitHub from GET cache or React render.
- Do not treat `worker_stage_scope_rows` as worker-backed execution evidence; it is only the required-stage checklist and pending-boundary manifest for a future explicit worker-batch task.
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
- `POST /api/storage/backtest-results/schema-seed` now creates a confirm-gated local `backtest_results` zero-row Parquet schema seed before schema acceptance. It writes only the ignored local schema file, writes no backtest result rows, writes no mock data, reads no row payloads or env files, calls no provider/model/GitHub service, and does not execute migration, manifest write, compaction, TTL refresh, trades, or production promotion.
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
- Storage overview/catalog now expose `storage_physical_execution_recipe` and rows. This local recipe fixes the future physical execution sequence for schema validation acceptance, confirm-gated manifest write/validate, schema migration, partition migration, compaction, TTL refresh, cleanup review, DuckDB post-migration validation, and production promotion. It keeps `execution_done=false`, `physical_execution_done=false`, `production_storage_complete=false`, `writes_parquet=false`, `refreshes_providers=false`, and `deletes_artifacts=false`.
- Storage overview/catalog now expose `storage_physical_execution_request` and rows. GET cache returns a missing placeholder until an explicit button POST creates a request; `POST /api/storage/physical-execution-request` binds user confirmation and the current `storage_physical_execution_recipe.physical_execution_scope_hash` for a future physical storage task while keeping `physical_task_created=false`, `physical_task_executed=false`, `writes_parquet=false`, `writes_manifest=false`, `deletes_artifacts=false`, `refreshes_providers=false`, and all provider/model/GitHub/trade/action flags false.
- Storage overview/catalog now expose `storage_physical_durable_evidence_recipe` and rows. This local durable-evidence recipe turns the remaining LTG-05 production proof gaps into named evidence keys for schema validation, manifest validation, partition migration, compaction, TTL refresh, cleanup review, DuckDB post-migration validation, and production promotion. It keeps `durable_evidence_complete=false`, `durable_promotion_ready=false`, `production_storage_complete=false`, `writes_parquet=false`, `writes_manifest=false`, `deletes_artifacts=false`, `provider_refresh_called_by_recipe=false`, and all provider/model/GitHub/trade/action flags false.
- `scripts/storage_contract.py` is now part of the local push gate. It reads only local storage cache and dry-run packet builders, then verifies schema migration preflight, dataset version policy, schema validation dry-run, confirm-gated `backtest_results` zero-row schema seed, partition migration dry-run, compaction dry-run, cache TTL dry-run, artifact cleanup review, DuckDB query service, physical execution request ticket, and storage dry-run/request task gating remain local/no-provider/no-trade while `production_storage_complete=false`.
- The same contract now emits `physical_migration_stage_scope_rows` for `physical_schema_validation`, `schema_migration`, `dataset_version_manifest_validation`, `partition_migration`, `physical_compaction`, `cache_ttl_refresh`, `artifact_cleanup_review`, and `production_promotion`. Each row is a pending local stage-scope manifest: required before production, no Parquet writes, no row-payload reads, no provider/model/GitHub calls, no cleanup delete execution, no trades, and no production storage completion.
- Migration Status now observes the LTG-05 `storage_physical_migration_stage_scope_manifest` from the local static Storage contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the eight remaining physical storage stages and no-write/no-delete/no-provider boundaries without writing Parquet/manifest, reading row payloads, deleting artifacts, calling providers/models/GitHub, mutating strategy action, or completing production storage.
- Migration Status now lists the LTG-05 local storage receipt sequence as seven separate steps: `backtest_results` zero-row schema seed, schema acceptance, manifest dry-run, manifest review, confirm-gated manifest write, manifest validate, and physical execution request. This is a progress accelerator for the next safe local button only; it does not turn a schema seed, schema/manifest packet, or execution-request ticket into Parquet migration, compaction, TTL refresh, cleanup delete, provider refresh, mock backtest evidence, or production storage evidence.

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
- `storage_physical_execution_recipe.status=storage_physical_execution_recipe_ready_execution_pending` is expected while physical execution evidence is missing; it is an execution sequence recipe, not physical schema validation, manifest validation, migration, compaction, TTL refresh, cleanup delete, or production promotion evidence.
- `storage_physical_execution_request.status=storage_physical_execution_request_ready_manual_physical_tasks_pending` is expected after the explicit request POST; it is a scope-bound request ticket for future physical storage tasks, not task creation, task execution, Parquet write evidence, manifest validation evidence, cleanup delete evidence, provider refresh evidence, or production storage completion.
- `storage_physical_durable_evidence_recipe.status=storage_physical_durable_evidence_recipe_ready_production_pending` is expected while durable production evidence is missing; it is a local evidence-gap checklist, not physical execution, Parquet write evidence, manifest write evidence, cleanup delete evidence, provider refresh evidence, or production storage completion.
- The `physical_migration_stage_scope_rows` manifest fixes the required production storage stage list and no-execution boundaries, but it is still a local contract. It does not create physical artifact evidence, manifest validation evidence, migration output, compaction output, TTL refresh output, cleanup delete evidence, or production promotion evidence.
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
- Storage overview/catalog expose `storage_physical_execution_recipe` and execution rows showing the ordered physical execution phases, required evidence, not-allowed shortcuts, no GET migration, no Parquet write, no manifest write, no provider refresh, no artifact delete, no trades, no `strategy action` mutation, and `production_storage_complete=false`.
- Storage overview/catalog expose `storage_physical_execution_request` and request rows. GET remains placeholder-only until explicit POST; successful POST must bind `approved_by_user=true`, the latest recipe scope hash, future target route/type, and every no-write/no-delete/no-provider/no-model/no-GitHub/no-trade/no-action flag while keeping `physical_task_created=false`, `physical_task_executed=false`, and `production_storage_complete=false`.
- Storage overview/catalog expose `storage_physical_durable_evidence_recipe` and durable evidence rows showing the required production proof keys, missing durable evidence, forbidden shortcuts, no GET cache writes, no Parquet write, no manifest write, no artifact delete, no provider/model/GitHub calls, no trades, no `strategy action` mutation, and `production_storage_complete=false`.
- `scripts/storage_contract.py` passes in the push gate while still reporting `production_storage_complete=false`, `physical_schema_validation_done=false`, `schema_migration_executed=false`, `dataset_version_manifest_validated=false`, `partition_migration_executed=false`, `physical_compaction_executed=false`, `cache_ttl_refresh_executed=false`, and `artifact_cleanup_delete_executed=false`; it also verifies manifest evidence remains read-only and no-writer/no-payload.
- `scripts/storage_contract.py` now verifies manifest hash evidence stays local and safe: dry-run proposed manifests must include a SHA-256 fingerprint, and read-only evidence must either expose a valid SHA-256 hash for an existing local manifest or remain empty when the manifest is missing.
- `physical_migration_stage_scope_rows` must list all required production storage stages: `physical_schema_validation`, `schema_migration`, `dataset_version_manifest_validation`, `partition_migration`, `physical_compaction`, `cache_ttl_refresh`, `artifact_cleanup_review`, and `production_promotion`. Every row must keep physical execution and production-completion flags false, no Parquet writes on GET, no Parquet writes by the contract, no row-payload reads, no provider/model/GitHub calls, no cleanup delete execution, no real trades, and no `strategy action` mutation.
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
- Do not treat `storage_physical_execution_recipe` as physical execution evidence, Parquet write evidence, manifest validation evidence, provider refresh evidence, cleanup delete evidence, production promotion, or production storage completion.
- Do not treat `storage_physical_execution_request` as physical execution, physical task creation, Parquet write evidence, manifest write/validation evidence, cleanup delete evidence, provider refresh evidence, production promotion, or production storage completion; it is only a user-confirmed scope-bound request ticket for a future explicit physical storage task.
- Do not treat `storage_physical_durable_evidence_recipe` as physical execution, Parquet write evidence, manifest write evidence, manifest validation evidence, provider refresh evidence, cleanup delete evidence, production promotion, or production storage completion; it is only the durable-evidence gap checklist for future explicit storage tasks.
- Do not treat `physical_migration_stage_scope_rows` as physical storage execution evidence; it is only the required-stage checklist and pending-boundary manifest for future explicit storage migration/review tasks.
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
- `POST /api/worker/activation-review` now creates a button-gated local `worker_activation_review_task_receipt` after the synthetic healthcheck. It records explicit operator approval, local task/status/log evidence, activation receipt visibility, production blockers, and safe call ledger while keeping `starts_celery_worker=false`, `pings_redis=false`, `starts_scheduler=false`, `task_dispatched=false`, `production_worker_complete=false`, and all Tushare/DeepSeek/GitHub flags false.
- `POST /api/worker/production-evidence-plan` now creates a button-gated local `worker_production_evidence_plan_receipt` after activation review. It records an operator-approved runtime-QA scope ticket for Celery process evidence, Redis broker evidence, cross-process controls, append-only worker logs, scheduler default-off runtime evidence, provider/model no-autoschedule, and no-trade/no-action boundaries while keeping `starts_celery_worker=false`, `pings_redis=false`, `starts_scheduler=false`, `task_dispatched=false`, `production_worker_complete=false`, and all Tushare/DeepSeek/GitHub flags false.
- `POST /api/worker/runtime-qa-execution-request` now creates a button-gated local `worker_runtime_qa_execution_request_receipt` after the production evidence plan. It binds operator approval, `scope_ticket_sha256`, and `runtime_qa_scope_hash` for a future runtime QA task while keeping `runtime_qa_task_created=false`, `runtime_qa_task_executed=false`, `starts_celery_worker=false`, `pings_redis=false`, `starts_scheduler=false`, `task_dispatched=false`, `production_worker_complete=false`, and all Tushare/DeepSeek/GitHub flags false.
- Worker runtime now exposes `worker_runtime_qa_execution_recipe`: a local runtime-QA sequence for the later production worker acceptance pass. It fixes the evidence-plan scope ticket, manual Celery process start, redacted Redis broker reachability, queue binding and synthetic round trip, cross-process retry/cancel/lock/dedupe, append-only worker log validation, scheduler default-off runtime, provider/model no-autoschedule boundary, local fallback rollback, and production worker promotion review phases while keeping `runtime_qa_done=false`, `production_worker_complete=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, and `task_dispatched=false`.
- Worker runtime now exposes `worker_runtime_durable_evidence_recipe`: a local durable-evidence checklist that ties blocker audit, healthcheck QA, task-log audit, queue routing, readiness/activation receipts, production evidence plan, and runtime QA recipe to the still-missing direct evidence rows for Celery process, Redis broker reachability, live queue round trip, cross-process controls, append-only worker logs, scheduler runtime proof, provider/model no-autoschedule proof, local fallback rollback, and production promotion review. It keeps `durable_evidence_complete=false`, `durable_promotion_ready=false`, `runtime_qa_done=false`, `production_worker_complete=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, `task_dispatched=false`, and all Tushare/DeepSeek/GitHub flags false.
- `scripts/worker_contract.py` is now part of the local push gate. It validates worker cache, dispatch plan, production blocker audit, healthcheck QA, task-log persistence audit, synthetic healthcheck explicit-POST boundary, activation review, production evidence plan scope ticket, readiness receipt, runtime QA recipe, durable evidence recipe, scheduler default-off, no-external-call, no-provider-call, no-trade, and no-action boundaries while `production_worker_complete=false`.
- The same contract now emits `worker_runtime_evidence_stage_scope_rows` for `celery_process`, `redis_broker`, `cross_process_retry_cancel_lock_dedupe`, `append_only_worker_logs`, `scheduler_default_off_runtime`, `provider_model_no_autoschedule_boundary`, and `no_trade_no_action_boundary`. Each row is a pending local runtime-evidence manifest: selected by the evidence-plan scope ticket, required before production, no process start, no Redis ping, no scheduler start, no task dispatch, no provider/model calls, no trades, and no production worker completion.
- Migration Status now observes the LTG-06 `worker_runtime_evidence_stage_scope_manifest` from the local static Worker contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the eight runtime-evidence stages, including local fallback round-trip evidence plus the remaining Celery/Redis blockers, and no-process/no-Redis/no-dispatch/no-provider boundaries without starting Celery, pinging Redis, starting APScheduler, dispatching tasks, calling providers/models/GitHub, mutating strategy action, or completing production worker readiness.
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
- The worker production evidence plan is still a local scope ticket for later runtime QA. It does not collect Celery process proof, Redis broker proof, cross-process control proof, append-only worker log proof, scheduler runtime proof, or production promotion approval.
- The `worker_runtime_qa_execution_request_receipt` is still a local request ticket. It binds approval and scope hashes for a future runtime QA task, but it does not create or execute that task, start Celery, ping Redis, dispatch work, collect runtime evidence, or prove production worker completion.
- The `worker_runtime_qa_dry_run_receipt` is still a local dry-run ticket. It binds the current request ticket id, evidence-plan scope hash, and runtime recipe hash, but it does not create or execute runtime QA, start Celery, ping Redis, dispatch work, collect runtime evidence, or prove production worker completion.
- The `worker_runtime_qa_execution_recipe` is still a local execution sequence. It does not start Celery, ping Redis, bind queues, dispatch synthetic tasks, prove cross-process controls, verify append-only worker logs, start scheduler, prove provider/model runtime boundaries, or prove production worker completion.
- The `worker_runtime_durable_evidence_recipe` is still a local durable-evidence checklist. It does not collect Celery process evidence, Redis broker reachability, live queue round-trip evidence, cross-process controls, append-only worker log evidence, scheduler runtime proof, provider/model runtime proof, local fallback rollback proof, or production promotion review.
- The `worker_runtime_evidence_stage_scope_rows` manifest fixes the required runtime evidence stage list and no-execution boundaries, but it is still a local contract. It does not collect Celery process evidence, Redis broker evidence, cross-process control evidence, append-only log evidence, scheduler runtime proof, provider/model runtime proof, or production promotion evidence.

### Implementation Phases

1. Keep local fallback stable.
2. Keep the dispatch plan matrix current as tasks are added, so future Celery/Redis routing has an auditable contract before execution is enabled.
3. Keep `worker_queue_routing_contract` current so provider/model/probe queues stay isolated from local queues before Celery routing is enabled.
4. Keep `worker_healthcheck_qa_contract` current so the future worker healthcheck has an explicit acceptance checklist before execution is enabled.
5. Keep `worker_task_log_persistence_audit` current so local safe task-log visibility is traceable while append-only/cross-process worker log proof remains pending.
6. Keep `POST /api/worker/synthetic-healthcheck` button-gated and local-only so task/status/log round-trip evidence remains visible before Celery/Redis activation.
7. Keep `worker_production_readiness_receipt` current so the next safe step is visible without converting local contracts into production completion evidence.
8. Keep `worker_production_activation_receipt` current so production-start blockers remain visible without starting processes.
9. Keep `worker_production_evidence_plan_receipt` current so later runtime QA has a scoped evidence ticket without converting the ticket into runtime evidence or production completion.
10. Keep `worker_runtime_qa_execution_request_receipt` current so later runtime QA can be requested with bound scope hashes without creating or executing the runtime task from the request.
11. Keep `worker_runtime_qa_dry_run_receipt` current so the request ticket and runtime recipe can be locally rehearsed without creating or executing runtime QA.
12. Keep `worker_runtime_qa_execution_recipe` current so the future runtime QA pass has an ordered checklist before any process starts or broker pings are allowed.
13. Keep `worker_runtime_durable_evidence_recipe` current so production promotion cannot proceed until every direct durable evidence row is collected and reviewed.
14. Add Celery worker execution behind explicit configuration.
15. Add Redis broker configuration and health reporting without cache API pinging Redis.
16. Add retry/cancel/lock behavior for real worker tasks.
17. Keep scheduler default off.

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
- Worker activation review task rows are visible in UI; before POST they remain `worker_activation_review_task_pending`, and after approved local review they may become `worker_activation_review_task_ready_production_blocked` while still requiring Celery/Redis process evidence, cross-process controls, append-only logs, scheduler runtime QA, and production promotion evidence.
- Worker production evidence plan rows are visible in UI; before approved activation review they remain `worker_production_evidence_plan_pending_activation_review`, and after approved evidence planning they may become `worker_production_evidence_plan_ready_runtime_qa_pending` with a 64-character `scope_ticket_sha256` while still requiring Celery process evidence, Redis broker evidence, cross-process controls, append-only logs, scheduler runtime QA, runtime reviewer approval, and production promotion evidence.
- Worker runtime QA execution request rows are visible in UI; before POST they remain `worker_runtime_qa_execution_request_missing`, and after approved evidence-plan + recipe scope binding they may become `worker_runtime_qa_execution_request_ready_manual_runtime_qa_pending` while still keeping `runtime_qa_task_created=false`, `runtime_qa_task_executed=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, `task_dispatched=false`, and `production_worker_complete=false`.
- Worker runtime QA dry-run rows are visible in UI; before POST they remain `worker_runtime_qa_dry_run_missing`, and after approved request-ticket + scope-hash binding they may become `worker_runtime_qa_dry_run_ready_execution_pending` while still keeping `runtime_qa_task_created=false`, `runtime_qa_task_executed=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, `task_dispatched=false`, and `production_worker_complete=false`.
- Worker runtime QA execution recipe rows are visible in UI/cache; they must list the full manual runtime sequence, keep every phase `runtime_qa_done=false`, keep process/network/task dispatch flags false, keep provider/model/probe calls false, and keep `production_worker_complete=false` until direct runtime QA evidence exists.
- Worker runtime durable evidence recipe rows are visible in UI/cache; they must list the full production evidence checklist, keep Celery process, Redis broker, queue round-trip, cross-process controls, append-only worker logs, scheduler runtime proof, provider/model runtime proof, local fallback rollback, and production promotion review as blocked until direct evidence exists, and keep all process/network/task dispatch/provider/model/trade/action/secret flags safe.
- `worker_runtime_evidence_stage_scope_rows` must list all required runtime evidence stages: `celery_process`, `redis_broker`, `cross_process_retry_cancel_lock_dedupe`, `append_only_worker_logs`, `scheduler_default_off_runtime`, `provider_model_no_autoschedule_boundary`, and `no_trade_no_action_boundary`. Every row must keep worker start, Redis ping, scheduler start, task dispatch, provider/model task dispatch, healthcheck execution, append-only log proof, activation readiness, production completion, external calls, real trades, and `strategy action` mutation false.
- Worker readiness receipt rows are visible in UI, `allowed_next_step=explicit_post_worker_synthetic_healthcheck_then_manual_activation_review`, and `not_allowed_next_steps` explicitly blocks GET cache process start, Redis ping, scheduler start, task dispatch, unconfigured provider/model scheduling, and treating the receipt or synthetic healthcheck as production completion.
- Worker production activation receipt rows are visible in UI, `allowed_next_step=explicit_synthetic_healthcheck_then_manual_celery_redis_activation_review`, and `not_allowed_next_steps` explicitly blocks GET cache process start, Redis ping, scheduler start, task dispatch, unconfigured provider/model scheduling, and treating the activation receipt as production worker completion.
- `scripts/worker_contract.py` passes in the local push gate while reporting `production_worker_complete=false`, `healthcheck_executed=false`, `task_log_persistence_verified=false`, `append_only_worker_log_verified=false`, `activation_ready=false`, `worker_started=false`, `redis_pinged=false`, `scheduler_started=false`, `worker_queue_routing_contract_ready=true`, `worker_production_readiness_receipt_ready=true`, `worker_production_activation_receipt_ready=true`, and `worker_production_evidence_plan_status` visible.
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
- Do not report `worker_activation_review_task_receipt` as Celery/Redis process proof, Redis broker reachability, scheduler startup, task dispatch, provider/model execution, or production worker completion.
- Do not report `worker_production_readiness_receipt` as worker startup, Redis reachability, scheduler startup, task dispatch, healthcheck execution, activation approval, or production worker completion.
- Do not report `worker_production_activation_receipt` as synthetic healthcheck execution, Celery worker startup, Redis reachability, scheduler startup, task dispatch, manual activation approval, provider/model scheduling evidence, or production worker completion.
- Do not report `worker_production_evidence_plan_receipt` or its `scope_ticket_sha256` as Celery/Redis process proof, Redis broker reachability, cross-process control proof, append-only worker log proof, scheduler runtime proof, runtime QA completion, provider/model execution, or production worker completion.
- Do not report `worker_runtime_qa_execution_request_receipt` as runtime QA task creation, runtime QA execution, Celery/Redis process proof, Redis broker reachability, queue binding proof, task dispatch proof, provider/model execution, durable evidence, or production worker completion.
- Do not report `worker_runtime_qa_dry_run_receipt` as runtime QA task creation, runtime QA execution, Celery/Redis process proof, Redis broker reachability, queue binding proof, task dispatch proof, provider/model execution, durable evidence, or production worker completion.
- Do not report `worker_runtime_qa_execution_recipe` as runtime QA evidence, Celery process proof, Redis broker reachability, queue binding proof, synthetic task dispatch proof, cross-process task control proof, append-only worker log proof, scheduler runtime proof, runtime QA completion, or production worker completion.
- Do not report `worker_runtime_durable_evidence_recipe` as runtime QA execution, Celery process proof, Redis broker reachability, queue round-trip proof, cross-process task control proof, append-only worker log proof, scheduler runtime proof, provider/model runtime proof, local fallback rollback proof, durable evidence completion, production promotion approval, or production worker completion.
- Do not report `worker_runtime_evidence_stage_scope_rows` as Celery/Redis process proof, Redis broker reachability, cross-process control proof, append-only worker log proof, scheduler runtime proof, provider/model execution, no-trade runtime QA completion, or production worker completion.
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
- Factor Quant Hub now exposes `deepseek_retry_repair_dry_run_contract`: a local no-model-call retry/repair dry-run that validates direct JSON, fenced JSON extraction, embedded JSON extraction, illegal-field sanitization, and parse-failed discard rows. It keeps provider retry execution, provider response-format enforcement, larger benchmark, token-cost evidence, and production DeepSeek automation blocked.
- Factor Quant Hub now exposes `deepseek_production_activation_receipt` and rows: a local LTG-07 next-step receipt that ties manual/default-off governance, sanitizer whitelist, JSON stability audit, response-format review, provider benchmark blockers, provider response_format blockers, bounded retry/repair blockers, token/cost evidence, auto_after_task activation, no GET/render model call, and no numeric/action overwrite into one checklist. It keeps `production_deepseek_explanation_complete=false`.
- Factor Quant Hub now exposes `deepseek_provider_benchmark_execution_recipe` and rows: a local no-model-call execution recipe for the future explicit provider benchmark. It fixes the minimum sample count, JSON success threshold, response-format requirement, bounded retry/repair cap, model-ledger fields, sanitizer/parse-failed review, token/cost review, auto-after-task gate, and production promotion review while keeping `provider_benchmark_done=false` and `production_deepseek_explanation_complete=false`.
- Factor Quant Hub now exposes a button-gated `POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket` preflight. It writes `deepseek_provider_benchmark_scope_ticket_receipt` and rows with explicit approval, sample count, response_format, retry budget, model-ledger fields, phase keys, server-side secret presence boolean, and a SHA-256 scope hash for the future provider benchmark. It does not call DeepSeek, does not read or expose credential names/values, does not prove provider benchmark execution, and keeps `provider_benchmark_done=false` / `production_deepseek_explanation_complete=false`.
- Factor Quant Hub now exposes `deepseek_durable_evidence_recipe` and rows: a local LTG-07 durable-evidence checklist that ties manual/default-off governance, sanitizer whitelist, JSON stability audit, response-format review, retry/repair dry-run, production activation receipt, and provider benchmark execution recipe to the still-missing direct provider evidence for benchmark report, provider response_format execution, bounded retry/repair execution, model ledger/hash/dedupe, sanitizer/parse-failed provider review, token/cost evidence, auto_after_task mode gate, redaction review, and production promotion review. It keeps `durable_evidence_complete=false`, `provider_benchmark_done=false`, `provider_response_format_enforced=false`, `bounded_retry_repair_executed=false`, `token_budget_cost_evidence_complete=false`, `auto_after_task_production_ready=false`, and `production_deepseek_explanation_complete=false`.
- `scripts/deepseek_governance_contract.py` is now part of the local push gate. It validates manual/default-off governance, sanitizer whitelist behavior, parse-failed discard, JSON stability blockers, response-format review blockers, retry/repair dry-run rows, provider benchmark execution recipe, durable evidence recipe, button-gated task catalog, centralized model strategy, no-model-call, no-secret, no-trade, and no-action boundaries while production automatic explanation remains pending.
- `scripts/deepseek_governance_contract.py` now emits `deepseek_production_stage_scope_rows` for the eight production evidence stages: larger provider benchmark, provider response-format enforcement, bounded retry/repair execution, token/cost evidence, auto-after-task mode gate, model ledger/hash/dedupe, sanitizer/parse-failed discard evidence, and production promotion review. Every row remains local/pending and keeps provider benchmark, model execution, automatic production readiness, external calls, trades, action mutation, numeric overwrite, and secrets disabled.
- Migration Status now observes the LTG-07 `deepseek_production_stage_scope_manifest` from the local static DeepSeek governance contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the eight remaining DeepSeek production evidence stages and no-model/no-provider/no-action boundaries without calling DeepSeek, running a provider benchmark, enforcing provider response_format, executing bounded retry/repair, writing model-ledger proof, enabling auto-after-task, overriding numeric values, emitting strategy action, or completing production DeepSeek explanations.
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
- `deepseek_retry_repair_dry_run_contract.status=retry_repair_dry_run_ready_provider_execution_pending` is a local dry-run contract; it does not call DeepSeek, does not prove provider retry execution, does not prove bounded retry/repair readiness, and does not justify enabling automatic production explanation.
- `deepseek_production_activation_receipt.status=deepseek_activation_receipt_ready_provider_benchmark_pending` is a local activation receipt; it does not call DeepSeek, does not prove provider benchmark, does not enforce provider response_format, does not prove bounded retry/repair, and does not make `auto_after_task` production-ready.
- `deepseek_provider_benchmark_execution_recipe.status=deepseek_provider_benchmark_recipe_ready_model_execution_pending` is a local recipe only; it does not call DeepSeek, does not prove the larger benchmark, does not enforce provider response_format, does not prove retry/repair execution, and does not justify production promotion.
- `deepseek_provider_benchmark_scope_ticket_receipt.status=deepseek_provider_benchmark_scope_ticket_*` is a local POST preflight only; it binds a future provider benchmark scope hash and credential-presence boolean, but it does not call DeepSeek, does not prove benchmark success, and does not permit auto_after_task production promotion.
- `deepseek_durable_evidence_recipe.status=deepseek_durable_evidence_recipe_ready_production_pending` is a local durable-evidence checklist only; it does not call DeepSeek, does not prove provider benchmark success, does not prove provider response_format execution, does not prove bounded retry/repair execution, does not attach model-ledger/token-cost/redaction evidence, and does not justify production promotion.
- The DeepSeek governance push-gate contract is still a local guard only; provider-backed benchmark, provider response-format enforcement, bounded retry/repair execution, and production auto-after-task readiness remain pending.
- `deepseek_production_stage_scope_rows` is a local production scope manifest only; it does not prove any provider benchmark, provider response-format enforcement, bounded retry/repair execution, token/cost evidence, live model ledger, auto-after-task readiness, or production promotion.
- `live_light` DeepSeek is not implemented yet. It needs explicit config, mode display, input hash dedupe, model ledger, token budget display, safe retry/parse fallback, and rate limits before it can run automatically.

### Implementation Phases

1. Expand benchmark set with representative packets.
2. Tighten response format and retry/repair policy.
3. Track token budget and model choice per purpose.
4. Keep automatic explanation disabled unless explicitly enabled and bounded.
5. Promote `deepseek_json_stability_audit` from local readiness to real benchmark evidence only after provider-backed samples meet the target.
6. Add future `live_light` DeepSeek after-task behavior only after data tasks complete, with same-input hash dedupe and sanitizer-first writeback.
7. Keep the automatic output schema narrow: `summary`, `support_notes`, `suppress_notes`, `conflict_notes`, `missing_data_notes`, and `discipline_notes` only.
8. Promote retry/repair from local dry-run to provider-backed bounded execution only after a real model benchmark proves retries, repairs, parse-failed discard, ledger rows, and cost limits together.
9. Keep `deepseek_durable_evidence_recipe` current so production promotion cannot proceed until every direct provider evidence row is collected and reviewed.

### Acceptance Criteria

- JSON success rate > 90%.
- No illegal fields.
- No trading action leakage.
- No numeric overwrite.
- Token cost is predictable and auditable.
- Failure does not pollute local results.
- `deepseek_json_stability_audit` must show `production_ready=true` only after JSON success rate exceeds 90%, larger benchmark is complete, and response format is enforced.
- `deepseek_response_format_review_contract` must keep `production_ready=false` until provider-level response format enforcement, bounded retry/repair policy, and larger benchmark evidence are all proven.
- `deepseek_retry_repair_dry_run_contract` may show `local_retry_repair_dry_run_ready=true` only for local extraction/sanitizer/parse-failed cases, while `retry_repair_policy_ready=false`, `bounded_retry_repair_ready=false`, `provider_retry_repair_executed=false`, and `production_deepseek_explanation_complete=false` stay visible until provider-backed evidence exists.
- `deepseek_production_activation_receipt` must keep `provider_benchmark_done=false`, `provider_response_format_enforced=false`, `bounded_retry_repair_ready=false`, `token_budget_cost_evidence_complete=false`, `auto_after_task_production_ready=false`, and `production_deepseek_explanation_complete=false` until the explicit provider-backed acceptance sequence is complete.
- `deepseek_provider_benchmark_execution_recipe` must require at least 40 provider benchmark samples, JSON success rate >90%, provider response-format enforcement, bounded retry/repair evidence, per-sample model ledger, token/cost review, redaction review, and manual promotion review while keeping all model-call and production-completion flags false.
- `deepseek_durable_evidence_recipe` rows must list provider benchmark report, provider response_format execution, bounded retry/repair execution, model ledger/hash/dedupe evidence, sanitizer/parse-failed provider review, token/cost evidence, auto_after_task mode gate, redaction review, and production promotion review as blocked until direct provider evidence exists, while keeping model-call, external-call, trade, action, numeric-overwrite, and secret flags safe.
- `scripts/deepseek_governance_contract.py` passes in the local push gate while reporting `provider_benchmark_done=false`, `response_format_enforced=false`, `retry_repair_policy_ready=false`, `retry_repair_dry_run_ready=true`, `auto_after_task_production_ready=false`, `deepseek_production_activation_receipt_ready=true`, `deepseek_durable_evidence_recipe_ready=true`, and `production_deepseek_explanation_complete=false`.
- `deepseek_production_stage_scope_rows` must list all eight production evidence stages and keep `provider_benchmark_done=false`, `response_format_enforced=false`, `bounded_retry_repair_executed=false`, `token_budget_cost_evidence_complete=false`, `auto_after_task_production_ready=false`, `model_execution_implemented=false`, `production_deepseek_explanation_complete=false`, external calls false, trades false, action mutation false, numeric overwrite false, and `contains_secret=false`.
- GET cache and React render must keep `model_call_status=not_called`.
- Future `live_light` DeepSeek may only run through POST task / worker after data readiness, must record model used, status, token usage, parse status, cache hit/miss, input hash, and output hash, and must keep failed parse out of the packet.
- Future `live_light` DeepSeek output must be sanitized to the six-field explanation schema: `summary`, `support_notes`, `suppress_notes`, `conflict_notes`, `missing_data_notes`, and `discipline_notes`.
- Same `input_hash` should not trigger duplicate model calls inside the configured dedupe window.
- UI model-ledger display must include `model_used`, `status`, `token_usage`, `parse_status`, `cache_hit/miss`, `input_hash`, and `output_hash` without exposing prompt secrets, raw token values, or unredacted provider errors.

### Forbidden

- Do not call DeepSeek on page render or GET cache.
- Do not treat future `live_light` after-task DeepSeek as a render call; it must remain a task with dedupe, mode gating, and audit fields.
- Do not enable DeepSeek `live_light` by default before benchmark, response-format, retry/repair, and token budget gates are accepted.
- Do not use DeepSeek as a data source.
- Do not let model output overwrite prices, positions, factor values, operation zones, or action.
- Do not treat local sanitizer/prompt audit as production automatic explanation readiness.
- Do not treat response-format review as provider-level response format enforcement or production benchmark completion.
- Do not treat retry/repair dry-run rows as provider retry execution, bounded retry/repair readiness, DeepSeek JSON stability proof, or production automation permission.
- Do not treat `deepseek_production_activation_receipt` as provider benchmark success, provider response_format enforcement, bounded retry/repair readiness, token-cost production proof, `auto_after_task` production readiness, or production DeepSeek explanation completion.
- Do not treat `deepseek_provider_benchmark_execution_recipe` as provider benchmark execution, response-format proof, retry/repair proof, token/cost evidence, redaction review, or production DeepSeek promotion.
- Do not treat `deepseek_provider_benchmark_scope_ticket_receipt` as provider benchmark execution, response-format proof, retry/repair proof, token/cost evidence, redaction review, credential validation, or production DeepSeek promotion.
- Do not treat `deepseek_durable_evidence_recipe` as provider benchmark execution, provider response_format proof, bounded retry/repair proof, model-ledger proof, token/cost evidence, redaction approval, `auto_after_task` readiness, durable evidence completion, production promotion approval, or production DeepSeek explanation completion.
- Do not treat `scripts/deepseek_governance_contract.py` passing as real provider benchmark success, provider response-format enforcement, bounded retry/repair readiness, auto-after-task production readiness, or production DeepSeek explanation completion.
- Do not treat `deepseek_production_stage_scope_rows` as provider benchmark evidence, provider response-format evidence, bounded retry/repair execution evidence, token/cost proof, live model ledger proof, auto-after-task readiness, or production DeepSeek promotion.

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
- The cache payload now exposes `next_session_legacy_parity_execution_recipe` and rows. This local no-feature-loss recipe fixes the future Streamlit-to-React comparison scope for latest close anchor, scenario paths, reference/limit lines, operation zones, position conflict warnings, freshness/data trust, DeepSeek status display, hover/click drilldown, and the read-only action boundary. It keeps `execution_done=false`, `streamlit_parity_complete=false`, and `production_replacement_complete=false`.
- The cache payload now exposes `next_session_browser_qa_runbook_contract`, `next_session_browser_qa_evidence_summary`, `next_session_browser_qa_review_contract`, and their rows. These fields pin the `#next` route, desktop/laptop/tablet/mobile viewport matrix, ignored `.stock_ming_3/motion_qa` artifact policy, default-motion and reduced-motion coverage, local evidence gaps, and explicit review state without opening a browser or submitting screenshots.
- `POST /api/next-session/browser-qa-review` is a button-gated local artifact review. It only reads ignored local runner reports for `#next`, records `next_session_browser_qa_review_contract`, and keeps `streamlit_parity_complete=false` and `production_replacement_complete=false`.
- `scripts/next_session_map_contract.py` is now part of the local push gate. It validates the exact ECharts payload, interaction readiness, reference/zone/position/DeepSeek visibility, GET cache envelope, button-gated local task, `#next` browser QA runbook/evidence/review boundaries, and React API-client/read-only boundaries while keeping `streamlit_parity_complete=false`, `production_replacement_complete=false`, `browser_visual_qa_done=false`, and `browser_performance_trace_done=false`.
- `scripts/next_session_map_contract.py` now emits `production_replacement_stage_scope_rows` for the eight production replacement evidence stages: exact cache payload contract, hover/click interaction contract, Streamlit parity review, browser visual QA, browser performance trace, reduced-motion/accessibility QA, durable CI/release evidence, and production replacement promotion. Every row remains local/pending and keeps browser execution, artifact writes, provider/model calls, trades, frontend action computation, operation-zone mutation, and production replacement completion disabled.
- Migration Status now observes the LTG-08 `next_session_production_replacement_stage_scope_manifest` from the local static next-session contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show exact-payload/interaction local evidence, pending Streamlit parity, browser visual QA, performance trace, reduced-motion/accessibility QA, durable CI evidence, and production promotion blockers without opening a browser, writing artifacts, calling providers/models/GitHub, computing frontend action, modifying operation zones, or completing production ECharts replacement.

### Gaps

- Interaction can still be improved after the current readiness audit.
- Evidence hover/click contracts are visible, but legacy parity review remains pending.
- Operation zone details are visible through guardrail rows, but full legacy interaction comparison is incomplete.
- Position conflict visualization is present, but clarity can still be improved.
- Full parity with legacy Streamlit chart is incomplete.
- The replacement activation receipt and `#next` browser QA contracts are next-step checklists/local artifact summaries only; they do not run browser QA, complete Streamlit parity, create durable CI/release evidence, or promote production replacement.
- `next_session_legacy_parity_execution_recipe` is a recipe only; it does not capture a legacy Streamlit reference, does not run browser QA, does not prove no-feature-loss parity, and does not authorize production replacement.
- The Next-session map push-gate contract is local only; browser visual QA, performance trace, Streamlit parity, and production replacement remain pending.
- `production_replacement_stage_scope_rows` is a local stage-scope manifest only; it does not prove Streamlit parity, browser visual QA, browser performance trace, reduced-motion/accessibility QA, durable CI/release evidence, or production ECharts replacement.

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
- `next_session_legacy_parity_execution_recipe.local_recipe_ready=true` only means the no-feature-loss parity scope is explicit enough to run a future manual parity review. It must list legacy reference capture, same-packet React/ECharts snapshot, feature-by-feature parity matrix, hover/click parity, browser visual QA, performance trace, durable evidence, and replacement promotion while keeping all execution/completion flags false.
- `next_session_browser_qa_runbook_contract.local_runbook_ready=true` only means the `#next` route, viewport matrix, and artifact policy are fixed.
- `next_session_browser_qa_evidence_summary.local_browser_qa_evidence_found=true` only means ignored local runner reports were summarized; even passing local evidence is not CI/release evidence.
- `next_session_browser_qa_review_contract.local_browser_qa_review_ready=true` is allowed only after explicit POST review and complete local default/reduced-motion evidence, and still keeps `streamlit_parity_complete=false` and `production_replacement_complete=false`.
- `production_replacement_stage_scope_rows` must list all eight production replacement evidence stages and keep `streamlit_parity_complete=false`, `browser_visual_qa_done=false`, `browser_performance_trace_done=false`, `reduced_motion_accessibility_qa_done=false`, `durable_ci_evidence_complete=false`, `production_replacement_complete=false`, `browser_opened_by_contract=false`, `artifacts_written_by_contract=false`, external calls false, trades false, frontend action computation false, operation-zone mutation false, and `contains_secret=false`.
- Frontend does not compute action.
- Frontend does not mutate price, position, or `operation_zones`.
- `production_replacement_complete` remains false until legacy parity is actually complete.
- No legacy visual signal group may be dropped merely to make the React replacement easier or faster.

### Forbidden

- Do not calculate trade action in React.
- Do not rewrite backend packet values in the chart layer.
- Do not hide freshness or credibility warnings.
- Do not treat `scripts/next_session_map_contract.py` passing as browser visual QA, performance trace, Streamlit parity, or production ECharts replacement completion.
- Do not treat `next_session_replacement_activation_receipt` as browser visual QA, performance trace, Streamlit parity, durable evidence, or production ECharts replacement completion.
- Do not treat `next_session_legacy_parity_execution_recipe` as legacy Streamlit parity completion, browser visual QA, performance trace, durable evidence, no-feature-loss proof, or production ECharts replacement.
- Do not drop legacy signal groups to reduce replacement scope.
- Do not treat `next_session_browser_qa_evidence_summary` or `next_session_browser_qa_review_contract` as CI evidence, Streamlit parity, durable release evidence, or production ECharts replacement.
- Do not treat `production_replacement_stage_scope_rows` as Streamlit parity evidence, browser visual QA, performance trace, reduced-motion/accessibility QA, durable CI/release evidence, or production ECharts replacement promotion.

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
- `scripts/start_command_center_3.command` now provides a manual local 3.0 double-click launcher. It starts FastAPI and React/Vite only when the user runs it, prefers the project `.venv`, writes logs under ignored `.stock_ming_3/logs/`, opens the local Vite URL, and is exposed through `desktop_launcher_contract`; it is a dev/preflight daily entry, not a production packaged app.
- Desktop preflight now exposes `production_package_readiness_receipt`: a local next-step receipt that ties production readiness, runtime contract, artifact detection, backend-offline UX source contract, blocker audit, and packaged QA matrix into one LTG-09 checkpoint. It can mark `ready_for_explicit_tauri_build=true`, but keeps `production_package_complete=false`, `tauri_build_executed_by_receipt=false`, `npm_or_cargo_executed_by_receipt=false`, `tauri_runtime_started_by_receipt=false`, `packaged_app_opened_by_receipt=false`, `fastapi_started_by_receipt=false`, `config_values_read_by_receipt=false`, and `log_files_written_by_receipt=false`.
- `scripts/tauri_desktop_contract.py` is now part of the local push gate. It validates desktop preflight cache, production runtime contract, backend-offline UX source contract, packaged runtime QA matrix, release manifest contract, production blocker audit, production package readiness receipt, frontend secret boundary, and no-build/no-runtime/no-config/no-log/no-provider/no-trade boundaries while `production_package_complete=false`.
- `scripts/tauri_desktop_contract.py` now emits `production_package_stage_scope_rows` for the eight production package evidence stages: Tauri dev runtime smoke, repeatable Tauri build, `.app` bundle detection/QA, DMG distribution artifact detection, backend startup strategy runtime QA, packaged backend-offline UX QA, config/log runtime path QA, and macOS signing/notarization review. Every row remains local/pending and keeps build execution, app launch, FastAPI startup, config value reads, log writes, provider/model task dispatch, external calls, trades, secrets, and production package completion disabled.
- Migration Status now observes the LTG-09 `tauri_production_package_stage_scope_manifest` from the local static Tauri desktop contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the eight remaining desktop package evidence stages and no-build/no-runtime/no-config/no-log/no-provider/no-trade boundaries without running Tauri dev/build, opening a packaged app, starting FastAPI, reading config values, writing logs, calling Tushare/DeepSeek/GitHub, or completing production desktop packaging.
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
- `production_package_stage_scope_rows` is a local stage-scope manifest only; it does not prove Tauri dev runtime smoke, repeatable Tauri build, `.app`/DMG package QA, backend startup runtime behavior, packaged offline UX, config/log runtime path validation, signing/notarization, or production package completion.
- `ltg_stage_scope_observed_rows` showing LTG-09 only proves the global migration status can observe the local static Tauri stage manifest. It does not prove packaged runtime QA or production desktop package completion.
- `desktop_launcher_contract.status=local_launcher_ready_dev_only` means a manual local 3.0 entry exists. It does not prove Tauri production package, packaged runtime QA, sidecar startup, signing/notarization, provider/model acceptance, or Streamlit retirement.

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
- `production_package_stage_scope_rows` must list all eight package evidence stages and keep `tauri_dev_runtime_smoke_done=false`, `tauri_build_repeatability_done=false`, `app_bundle_detected=false`, `dmg_distribution_detected=false`, `backend_startup_runtime_validated=false`, `backend_offline_packaged_ux_verified=false`, `config_log_runtime_paths_validated=false`, `signing_notarization_done=false`, `production_package_complete=false`, build/runtime execution false, config value reads false, log writes false, external calls false, trades false, and `contains_secret=false`.

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
- Do not claim `production_package_stage_scope_rows` as Tauri dev runtime smoke, repeatable build evidence, `.app`/DMG artifact QA, backend runtime startup proof, packaged offline UX proof, config/log runtime validation, signing/notarization, or production desktop package completion.
- Do not claim `scripts/start_command_center_3.command` or a Desktop symlink as production packaged app completion.
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
- Legacy cache now exposes `streamlit_retirement_durable_evidence_recipe` and rows: a local LTG-10 durable-evidence recipe for route inventory, ordinary workflow parity, Candidate Radar no-feature-loss acceptance, provider-backed parity, browser/performance/visual QA, admin/debug decision, fallback retirement review, `app.py` removal-or-retention decision, guardrail regression, and production promotion. It keeps `durable_evidence_complete=false`, `durable_promotion_ready=false`, `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, and every Streamlit/tool/task/provider/model/trade/action side-effect flag disabled.
- `scripts/streamlit_legacy_contract.py` is now part of the local push gate. It validates legacy cache read-only policy, `legacy/admin/debug` marking, React/Tauri primary-entry policy, ordinary-workflow exit blockers, fallback dependency contract, no-feature-cut requirements, no Streamlit execution, no legacy tool execution, no task creation, no provider/model/GitHub calls, no trade, and no action mutation while `ordinary_workflow_exit_complete=false`.
- `scripts/streamlit_legacy_contract.py` now emits `streamlit_retirement_stage_scope_rows` for the eight retirement evidence stages: route inventory/primary-entry contract, ordinary workflow replacement parity, Candidate Radar replacement parity, provider-backed parity acceptance, browser/performance QA, admin/debug retention or replacement decision, fallback retirement review, and `app.py` removal or retention review. Every row remains local/pending and keeps Streamlit opening, legacy tool execution, task creation, fallback removal, `app.py` deletion, provider/model task dispatch, external calls, trades, holdings mutation, secrets, and full retirement completion disabled.
- Migration Status now observes the LTG-10 `streamlit_retirement_stage_scope_manifest` from the local static Streamlit legacy contract and surfaces it in `ltg_stage_scope_observed_rows`. This makes the global 14-LTG page show the eight remaining ordinary-workflow replacement and retirement evidence stages without opening Streamlit, running legacy tools, creating tasks, removing fallback, deleting `app.py`, calling Tushare/DeepSeek/GitHub, mutating holdings/action, or completing Streamlit retirement.
- It has not fully exited ordinary usage paths.

### Gaps

- React/Tauri does not yet cover every ordinary operation.
- Some old tools still need Streamlit fallback.
- `primary_workflow_exit_audit.status=ordinary_workflow_exit_partial_fallback_required` is expected until all ordinary workflows are proven in Command Center 3 and fallback removal is safe.
- `streamlit_retirement_readiness_receipt.status=streamlit_retirement_receipt_ready_fallback_blocked` is expected while Candidate Radar parity, full-pool/deep-scan acceptance, provider-backed parity, browser/performance QA, and admin/debug replacement or retirement decisions remain incomplete.
- `scripts/streamlit_legacy_contract.py` is a local regression guard only; it does not remove Streamlit fallback, prove replacement parity, run old tools, open Streamlit, or complete ordinary-workflow exit.
- `streamlit_retirement_stage_scope_rows` is a local stage-scope manifest only; it does not prove ordinary workflow replacement parity, Candidate Radar parity, provider-backed parity, browser/performance QA, admin/debug replacement/retention decisions, fallback retirement, `app.py` removal, or complete Streamlit exit.
- `ltg_stage_scope_observed_rows` showing LTG-10 only proves the global migration status can observe the local static Streamlit retirement stage manifest. It does not prove ordinary-workflow exit, fallback removal, admin/debug retirement, `app.py` removal, or full Streamlit retirement completion.
- `streamlit_retirement_durable_evidence_recipe` is a local durable-evidence recipe only; it does not collect direct parity evidence, run browser/performance QA, run provider-backed acceptance, decide admin/debug retention, remove fallback, delete `app.py`, approve promotion, or complete Streamlit exit.

### Implementation Phases

1. Identify ordinary user workflows still depending on Streamlit.
2. Migrate those workflows to React/Tauri + FastAPI.
3. Keep `streamlit_fallback_dependency_contract` current so every fallback dependency has a removal criterion and no feature-cut boundary.
4. Keep `streamlit_retirement_readiness_receipt` current so the next explicit parity/retirement review is visible without deleting fallback or marking completion.
5. Keep `streamlit_retirement_durable_evidence_recipe` current so the durable evidence needed for final retirement remains visible and reviewable.
6. Keep Streamlit for debug/admin/fallback only.
7. Preserve old-module guards.
8. Promote `primary_workflow_exit_audit` to complete only after route coverage has no fallback blockers and legacy removal is safe.

### Acceptance Criteria

- Ordinary users can use Command Center 3 desktop as the main surface.
- Streamlit does not auto-create tasks.
- Streamlit does not bypass guards.
- Legacy strong-action protection remains.
- `primary_workflow_exit_audit.ordinary_workflow_exit_complete=true` only when route coverage has no remaining Streamlit fallback dependencies and the migration checklist is clear.
- `streamlit_fallback_dependency_contract.full_streamlit_removal_ready=true` only when ordinary fallback dependencies and retained admin/debug fallback dependencies are all cleared with replacement parity proven.
- Streamlit retirement readiness receipt rows are visible in UI, `allowed_next_step=explicit_replacement_parity_review_then_streamlit_fallback_retirement_review`, and `not_allowed_next_steps` explicitly blocks GET cache opening Streamlit, running legacy tools, creating tasks, page render retiring fallback, deleting `app.py`, or treating the receipt as retirement completion.
- `scripts/streamlit_legacy_contract.py` passes in the local push gate while reporting `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, `streamlit_retirement_readiness_receipt_ready=true`, and `does_not_open_streamlit=true`.
- `streamlit_retirement_stage_scope_rows` must list all eight retirement evidence stages and keep `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, replacement parity false, provider-backed parity false, browser/performance QA false, admin/debug decision false, fallback removal false, `app.py` deletion false, external calls false, trades false, holdings mutation false, and `contains_secret=false`.
- `streamlit_retirement_durable_evidence_recipe` must list the 10 durable evidence keys and keep direct parity, provider-backed parity, browser/performance QA, admin/debug decision, fallback retirement, `app.py` decision, and production promotion blocked until direct evidence exists. It must keep `durable_evidence_complete=false`, `durable_promotion_ready=false`, `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, Streamlit opening false, legacy tool execution false, task creation false, external calls false, trades false, action/holding mutation false, and `contains_secret=false`.

### Forbidden

- Do not delete Streamlit fallback before replacement workflows are usable.
- Do not let legacy pages bypass freshness, model, or action guardrails.
- Do not present Streamlit as the primary 3.0 surface.
- Do not treat local exit audit as complete while status remains `ordinary_workflow_exit_partial_fallback_required`.
- Do not treat `streamlit_retirement_readiness_receipt` as fallback removal, `app.py` deletion, replacement parity, admin/debug retirement, or complete Streamlit exit.
- Do not treat `scripts/streamlit_legacy_contract.py` passing as Streamlit fallback removal, replacement parity, admin/debug retirement, or complete ordinary-workflow exit.
- Do not treat `streamlit_retirement_stage_scope_rows` as ordinary workflow parity, Candidate Radar parity, provider-backed parity, browser/performance QA, admin/debug retirement, fallback removal, `app.py` deletion, or complete Streamlit exit.
- Do not treat `streamlit_retirement_durable_evidence_recipe` as durable evidence completion, production promotion, fallback removal, `app.py` deletion, provider-backed acceptance, browser/performance QA, admin/debug decision, or complete Streamlit exit.

### Recommended Commit Message

```text
Retire Streamlit from primary user workflow
```

## LTG-11: 测试 / CI / Smoke / 安全扫描标准化

### Current Status

- Local test, frontend build, smoke, and diff checks are available.
- `scripts/push_gate_3_0.sh` now codifies the local push gate: Python tests, desktop build, smoke, diff check, high-risk secret scan, generated artifact scan, and final clean-worktree check.
- `scripts/data_health_freshness_contract.py` is now part of the local push gate. It validates LTG-01 Data Health contracts and the freshness production blocker audit remain cache-only, provider-backed acceptance stays pending, and score/support/preview/action boundaries are not silently weakened.
- `scripts/tushare_acceptance_contract.py` is now part of the local push gate. It validates LTG-02 Tushare matrix/readiness/contracts, provider evidence gap ledger, target-sample runbook, target-sample execution recipe, and scope-bound target-sample execution-request ticket remain button-gated, local, no-provider, no-trade, and no-action, while provider-backed full-interface acceptance remains pending.
- `scripts/bootstrap_runtime_contract.py` is now part of the local push gate. It validates the mode-layered runtime boundary: `cache_only` remains offline, `live_light` may create only a rate-limited local bootstrap plan/model-ledger skeleton, Tushare/DeepSeek remain uncalled by the contract, and provider/model execution stays pending.
- `scripts/tushare_deepseek_linkage_contract.py` is now part of the local push gate. It validates the cross-surface linkage between `live_light` bootstrap and searched-symbol quant projection: cache/render silence, POST task boundary, light Tushare scope, optional DeepSeek pro model-ledger schema, credential-presence booleans, no token/key exposure, no provider/model execution, no trade, and no action mutation remain visible before any real acceptance run.
- `scripts/factor_test_lab_contract.py` is now part of the local push gate. It validates LTG-03 Factor Test Lab research metrics, small-pool readiness, storage query consumption, production QA, provider validation blocker audit, provider small-pool dry-run scope ticket, execution recipe, and execution-request ticket stay local/research-only while provider-backed small-pool and full-market validation remain pending.
- `scripts/factor_universe_contract.py` is now part of the local push gate. It validates LTG-04 universe modes, local read-plan storage-query consumption, worker-batch dry-run and execution-request tickets, button-gated task catalog, React read-only display, partial-pool-not-full-market-proof visibility, no-provider/no-model/no-trade/no-action boundaries, and keeps worker batch execution, rank/zscore, neutralization, full-pool validation, and production universe research pending.
- `scripts/deepseek_governance_contract.py` is now part of the local push gate. It validates LTG-07 manual/default-off governance, sanitizer whitelist, parse-failed discard, JSON stability blockers, response-format review blockers, button gating, model strategy, no-model-call, no-secret, no-trade, and no-action boundaries while provider-backed benchmark and production automatic explanation remain pending.
- `scripts/next_session_map_contract.py` is now part of the local push gate. It validates LTG-08 exact ECharts payload, interaction readiness, reference/zone/position/DeepSeek visibility, current GET cache envelope, button-gated local task, React API-client/read-only display, no-browser, no-provider, no-trade, and no-action boundaries while browser visual QA, performance trace, Streamlit parity, and production replacement remain pending.
- `scripts/candidate_radar_contract.py` is now part of the local push gate. It validates LTG-13 Candidate Radar cache reads, local quick-scan task gating, full-pool/deep-scan plan-only boundaries, no-feature-loss QA, replacement-gap triage, promotion-blocker audit, result-delta clarity, and no-trade/no-action boundaries while production radar replacement remains pending.
- `scripts/storage_contract.py` is now part of the local push gate. It validates LTG-05 Storage cache, schema/version preflights, dry-run packets, DuckDB query policy, artifact cleanup review, physical execution request ticket, and storage task catalog gating remain local/no-write/no-provider/no-trade while physical storage production remains pending.
- `scripts/worker_contract.py` is now part of the local push gate. It validates LTG-06 Worker cache, dispatch plans, production blocker audit, healthcheck QA, activation review, scheduler default-off, no-external-call, no-provider-call, no-trade, and no-action boundaries while production worker activation remains pending.
- `scripts/tauri_desktop_contract.py` is now part of the local push gate. It validates LTG-09 desktop preflight cache, runtime contract, backend-offline UX source contract, packaged runtime QA matrix, production blocker audit, no-build/no-runtime/no-config/no-log/no-provider/no-trade boundaries, and keeps production desktop package completion pending.
- `scripts/streamlit_legacy_contract.py` is now part of the local push gate. It validates LTG-10 Legacy cache, ordinary-workflow exit audit, fallback dependency contract, React Legacy page boundaries, no-feature-cut requirements, no Streamlit execution, no legacy tool execution, no task creation, no-provider/no-model/no-GitHub/no-trade/no-action boundaries, and keeps Streamlit full retirement pending.
- `scripts/trade_isolation_contract.py` is now part of the local push gate. It validates LTG-12 risk cache trade-isolation audit, task catalog no-order/no-trade route boundaries, frontend no-trade/no-action visibility, no broker/order execution path, and future real-trading separation while real trading remains disconnected.
- `scripts/push_gate_3_0.sh` can optionally write a local Markdown release-readiness report when `PUSH_GATE_REPORT_PATH` is set; report generation runs before the final clean-worktree check so unignored in-repo reports still block push.
- Secret/artifact keyword hits are separated into high-risk failures versus review output so sanitizer/test/docs mentions can be explained instead of silently ignored.
- `scripts/secret_keyword_review_contract.py` now gives the ordinary keyword scan a structured local contract: it classifies tracked keyword hits by category and top files, emits counts only, suppresses raw source lines, and fails if high-risk tracked secret-looking values appear outside tests/docs. It does not call external services or prove periodic human allowlist review is complete.
- `GET /api/audit/cache` now exposes `release_gate_readiness_audit`, `release_gate_readiness_rows`, and local workflow inventory. This is a static local contract check for `scripts/push_gate_3_0.sh`, not a CI status check and not production completion proof.
- `GET /api/audit/cache` now exposes `release_gate_push_readiness_receipt` and `release_gate_push_readiness_rows`: a local-only receipt that selects the safe sequence `run_scripts_push_gate_3_0_then_git_push_then_inspect_remote_actions_if_needed`. It keeps fresh local gate output, matching remote Actions status, latest green run evidence, and periodic allowlist review as separate evidence items.
- `GET /api/audit/cache` now exposes `release_gate_stage_scope_rows` for the eight release-gate evidence stages: local push-gate static contract, fresh local gate command run, secret/artifact allowlist review, CI mirror workflow contract, matching remote Actions status, failure-email triage evidence, release-readiness report artifact policy, and explicit push approval boundary. Every row remains local/pending and keeps fresh gate observation, remote Actions status, latest remote green evidence, failure-email dismissal, allowlist review, release-gate completion, GitHub API calls, external calls, provider/model calls, trades, secrets, and push execution disabled.
- Migration Status now observes the LTG-11 `release_gate_stage_scope_manifest` through the same local release-gate static helpers surfaced by `GET /api/audit/cache`, and surfaces it in `ltg_stage_scope_observed_rows`. This makes the 14-LTG overview show the eight release-gate evidence stages, local gate readiness, CI mirror presence, explicit push sequence readiness, and remaining remote/fresh-run blockers without running the gate, calling GitHub API, pushing, calling Tushare/DeepSeek, executing trades, or completing release readiness.
- `GET /api/audit/cache` now also exposes `ci_notification_triage_contract` and `ci_notification_triage_rows`: a local-only triage contract for GitHub Actions failure emails. It separates local push-gate readiness, static CI mirror presence, stale-email risk, and the remote failed step/log evidence still required from the Actions run page. It does not call GitHub API, fetch workflow logs, or prove the remote run is green.
- `.github/workflows/command-center-3-push-gate.yml` now mirrors the local push gate by creating `.venv`, installing desktop dependencies, and running `scripts/push_gate_3_0.sh` with `PYTHON_BIN=.venv/bin/python`.

### Gaps

- CI mirror workflow exists, but remote CI status is still not local proof until a pushed run is inspected; current audit only proves static workflow presence.
- Push readiness receipt is local and static: `local_receipt_ready=true` means the explicit gate/push/remote-review path is well defined, not that the gate has just run or that the latest remote run is green.
- `release_gate_stage_scope_rows` is a local stage-scope manifest only; it does not prove a fresh local gate run for current HEAD, matching remote Actions status, latest remote green evidence, failure email root cause, allowlist review completion, push approval, or release-gate completion.
- `ltg_stage_scope_observed_rows` showing LTG-11 only proves the global migration status can observe the local release-gate stage manifest. It does not run `scripts/push_gate_3_0.sh`, inspect GitHub Actions, dismiss failure emails, write a release report, approve push, or prove CI green.
- CI failure email triage is visible, but it only tells the user which remote evidence is required: matching commit/head, failed step name, and safe log excerpt. It cannot dismiss a failure email or mark CI green without that remote run evidence.
- Push gate still needs periodic review of false-positive allowlists; current audit keeps `false_positive_allowlist_review_pending` visible.
- Structured keyword review is present, but it is still a local classification contract; periodic human allowlist review and remote CI evidence remain separate.
- Tushare acceptance contract is present, but it is still a local matrix/readiness/evidence-gap/execution-request guard; real provider-backed interface samples remain a later LTG-02 acceptance phase.
- Bootstrap runtime contract is present, but it is still a local mode-layering guard; real `live_light` Tushare refresh, DeepSeek pro after-task execution, and intraday adapter calls remain later explicit acceptance phases.
- Tushare / DeepSeek linkage contract is present, but it is still a local cross-surface guard. It proves the handoff shape between runtime mode, bootstrap task, search quant projection, credential preflight, and ledger requirements; it does not call Tushare, call DeepSeek, prove JSON stability, refresh Factor/Next Session/ECharts, or promote production linkage.
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
- Bootstrap runtime contract runs after Tushare acceptance and before Factor Test Lab, and keeps `provider_execution_implemented=false`, `model_execution_implemented=false`, and no-provider/no-model/no-trade boundaries visible for `live_light`.
- Tushare / DeepSeek linkage contract runs after Bootstrap runtime and before Factor Test Lab, and keeps `production_live_light_complete=false`, `production_quant_projection_complete=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, credential values hidden, and Tushare/DeepSeek/GitHub calls false while the linkage acceptance path is visible.
- Factor Test Lab contract runs after the Tushare / DeepSeek linkage contract and before static UI QA, and keeps `provider_backed_small_pool_validation_done=false` / `production_factor_test_validation_complete=false` visible.
- Factor universe contract runs after Factor Test Lab and before DeepSeek governance, and keeps `large_universe_pipeline_done=false`, `full_pool_validation_done=false`, `cross_sectional_rank_zscore_done=false`, `neutralization_done=false`, `factor_combination_research_done=false`, and `production_factor_universe_complete=false` visible.
- DeepSeek governance contract runs after Factor universe and before Next-session map, and keeps `provider_benchmark_done=false`, `response_format_enforced=false`, `retry_repair_policy_ready=false`, `auto_after_task_production_ready=false`, and `production_deepseek_explanation_complete=false` visible.
- Next-session map contract runs after DeepSeek governance and before Candidate Radar, and keeps `streamlit_parity_complete=false`, `production_replacement_complete=false`, `browser_visual_qa_done=false`, and `browser_performance_trace_done=false` visible.
- Candidate Radar contract runs after Next-session map and before static motion QA, and keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, and `deep_scan_done=false` visible.
- Storage contract runs after Candidate Radar and before static motion QA, and keeps `production_storage_complete=false`, `schema_migration_executed=false`, `partition_migration_executed=false`, `physical_compaction_executed=false`, `cache_ttl_refresh_executed=false`, `physical_task_created=false`, and `physical_task_executed=false` visible.
- Worker contract runs after Storage and before static motion QA, and keeps `production_worker_complete=false`, `healthcheck_executed=false`, `activation_ready=false`, `worker_started=false`, `redis_pinged=false`, and `scheduler_started=false` visible.
- Tauri desktop contract runs after Worker and before static motion QA, and keeps `tauri_build_executed=false`, `packaged_runtime_qa_done=false`, `production_package_complete=false`, `does_not_run_tauri=true`, `does_not_run_npm=true`, and `does_not_run_cargo=true` visible.
- Streamlit legacy contract runs after Tauri desktop and before static motion QA, and keeps `ordinary_workflow_exit_complete=false`, `streamlit_fallback_removal_ready=false`, `full_streamlit_removal_ready=false`, `streamlit_fallback_retained=true`, and `does_not_open_streamlit=true` visible.
- Trade isolation contract runs after Streamlit legacy and before static motion QA, and keeps `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, and `future_real_trading_requires_separate_project=true` visible.
- `release_gate_readiness_audit.local_gate_ready=true` and `ci_mirror_ready=true` are visible in the audit cache, while `release_gate_complete` remains false until allowlist review and actual remote check evidence are proven.
- `release_gate_stage_scope_rows` must list all eight release-gate evidence stages and keep `fresh_local_gate_run_observed=false`, `remote_actions_status_known=false`, `latest_remote_run_verified_green=false`, `failure_email_has_matching_head_and_logs=false`, `can_dismiss_failure_email_without_matching_head_and_logs=false`, `periodic_allowlist_review_ready=false`, `release_gate_complete=false`, `stage_complete=false`, `did_not_push=true`, `github_api_called=false`, external calls false, provider/model calls false, trades false, and `contains_secret=false`.
- `ci_notification_triage_contract.status=ci_notification_triage_ready_remote_logs_required` is visible in the audit cache, while `remote_actions_status_known=false`, `remote_failure_logs_available=false`, `latest_remote_run_verified_green=false`, and `can_dismiss_failure_email_without_matching_head_and_logs=false` remain explicit until the failed Actions run is inspected.

### Forbidden

- Do not bypass failing tests.
- Do not use `git add .`.
- Do not push without user confirmation.
- Do not treat a local push-gate pass, static CI mirror, old email notification, or CI triage contract as proof that the latest remote Actions run passed.
- Do not treat `release_gate_stage_scope_rows` as a fresh local gate run, remote Actions proof, failure-email dismissal, allowlist review completion, user push approval, or release-gate completion.
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
- `scripts/trade_isolation_contract.py` now exposes a `trade_isolation_stage_scope_manifest` for the future real-trading path. It keeps the current app in research-client mode while listing the future stages that must be proven separately: no-broker boundary, no-order task catalog, no frontend trade controls, no model/provider action mutation, separate project decision, broker adapter design review, order endpoint security review, and paper/simulated trade sandbox.
- Migration Status now observes the LTG-12 `trade_isolation_stage_scope_manifest` from the local static trade-isolation contract and surfaces it in `ltg_stage_scope_observed_rows`. This completes 14/14 local stage-scope visibility while keeping the strict closeout at `0/14`: it shows current no-broker/no-order/no-frontend-trade/no-model-action-mutation boundaries and future real-trading project blockers without connecting broker/order APIs, submitting orders, approving paper trading, calling Tushare/DeepSeek/GitHub, or treating the release receipt as trading approval.

### Gaps

- Future productionization could accidentally blur research and execution boundaries.
- Any eventual trading integration would need a separate project, separate approvals, and separate safety design.
- The audit proves current Command Center 3 cache/task/frontend contracts, not a future broker/order integration design.
- The release receipt is not real-trading approval; it only records that the current research client remains isolated from broker/order execution.
- The push-gate contract is local and static; it blocks accidental boundary regression but does not prove broker integration safety, simulated trading, order routing, or production trade compliance.
- `ltg_stage_scope_observed_rows` showing LTG-12 only proves the global migration status can observe the local trade-isolation stage manifest. It does not approve a real-trading project, design a broker adapter, create an order endpoint, enable frontend trade controls, run a paper-trading sandbox, or make Command Center 3 a production trading terminal.
- The desired boundary is not an absolute forever-ban; it is a run-mode split. Research/cache/render/manual-review modes stay active, while any future execution mode must remain unavailable until the separate stage evidence exists.

### Implementation Phases

1. Keep all current 3.0 migration work research/client-side only.
2. Preserve action mutation guards in cache, task, frontend, model, factor, storage, and worker paths.
3. Add tests whenever a new route or task can affect decision-adjacent data.
4. Keep `trade_isolation_release_receipt` current so release candidates can state research-client safety without implying broker/order approval.
5. Keep the local trade-isolation push-gate contract updated whenever task routes, risk cache policy, packet registry boundaries, or frontend task controls change.
6. Treat any future real-trading work as a separate run mode with its own project approval, broker threat model, order endpoint security review, simulated-trade sandbox, audit trail, kill switch, and explicit operator approval.

### Acceptance Criteria

- No automatic order path exists.
- Research/factor/model/cache/frontend paths cannot mutate `strategy action`.
- Any future trade integration is explicitly out of this roadmap unless a separate approved design exists.
- `trade_isolation_audit.status=trade_isolation_ready`, with zero blockers and all known POST routes covered by the task catalog.
- `trade_isolation_release_receipt.status=trade_isolation_release_receipt_ready_research_release_only`, with `allowed_next_step=continue_research_client_release_or_create_separate_real_trading_project_design` and not-allowed shortcuts blocking broker adapters, order endpoints, model/factor-to-order paths, frontend trade submission, and treating the receipt as real-trading approval.
- `scripts/trade_isolation_contract.py` passes in the local push gate while reporting `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, `does_not_modify_holdings=true`, `trade_isolation_release_receipt_ready=true`, and `future_real_trading_requires_separate_project=true`.
- `trade_isolation_stage_scope_manifest` contains every required future stage, and each row keeps `real_trading_connected=false`, `broker_adapter_connected=false`, `order_endpoint_present=false`, `trade_execution_api_enabled=false`, `order_route_present=false`, `frontend_trade_controls_present=false`, `model_or_provider_can_modify_action=false`, `paper_trading_sandbox_ready=false`, `separate_project_approved=false`, `order_submitted=false`, and `future_real_trading_requires_separate_project=true`.

### Forbidden

- Do not connect broker/order APIs in ordinary migration work.
- Do not execute real trades.
- Do not let model or factor output become orders.
- Do not treat the local trade-isolation contract as approval to connect real broker/order execution; it only proves current isolation remains intact.
- Do not treat `trade_isolation_release_receipt` as approval to connect broker/order execution; it only proves the current research client stays isolated.
- Do not treat the stage-scope manifest as broker integration, paper-trading completion, order API approval, security review completion, or production trading readiness.

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
- Candidate radar packets now expose `fast_scan_task_pipeline_contract` and `fast_scan_task_pipeline_rows`: this local contract ties the non-blocking 3.0 radar workflow together: initial cache render stays read-only, explicit POST task boundaries remain visible, TaskLaunchReceipt / TaskStatusPanel carry task status, previous-cache fallback or pending state is visible, safe failure stays local, input budgets and worker boundary are displayed, no-feature-loss gaps remain visible, and production replacement stays blocked. It is a task-pipeline shape contract, not async worker execution, provider-backed parity, browser performance proof, or production replacement evidence.
- Candidate radar packets now expose `candidate_radar_production_activation_receipt` and `candidate_radar_production_activation_rows`: this local activation receipt converts the existing quick-scan receipt, no-feature-loss QA, promotion blockers, full-pool/deep-scan plans, provider-backed parity gap, browser visual/performance gap, legacy-retirement gate, and trade/action isolation into a single next-step checklist. It keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, and `durable_ci_evidence_complete=false`.
- Candidate radar packets now expose `legacy_parity_acceptance_receipt` and `legacy_parity_acceptance_rows`: this local receipt turns the old next-ticket radar's Top / Watch / Excluded split, evidence links, scoring dimensions, trigger / invalidation logic, holding comparison, candidate pool sources, scan filters, timeout fallback, manual deep research path, and output fields into explicit replacement gates. It is a no-feature-loss acceptance guard, not production replacement evidence; it keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `legacy_fallback_required=true`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `browser_visual_delta_qa_done=false`, and `browser_performance_trace_done=false`.
- Candidate radar packets now expose `result_delta_clarity_contract`, `result_delta_clarity_rows`, and `previous_cache_diff_rows`: candidate counts, display truncation, skipped reasons, provider gaps, freshness state, scan mode transitions, local-pool skips, and full/deep boundaries are visible without rescoring, refreshing providers, timers, browser QA, or trade/action mutation. When a previous SQLite radar packet exists, local scan tasks compute added/removed/rank/score/status deltas; when no previous packet exists, the missing baseline remains explicit.
- Candidate radar packets now expose `candidate_priority_explanation_contract` and rows: existing cache rank, existing score, action label, evidence summary, trigger/invalidation presence, and data gaps are explained per visible candidate without rescoring, reordering, refreshing providers, calculating action, or creating a trade signal.
- Candidate radar packets now expose `candidate_browser_qa_runbook_contract`, rows, and matrix rows. The runbook pins `#candidates`, desktop/laptop/tablet/mobile viewports, result-cluster readability, local-scan button visibility, result-delta gap visibility, mobile clipping checks, reduced-motion expectations, and the shared local browser runner. It does not open a browser or prove visual/performance acceptance.
- Candidate radar packets now expose `candidate_browser_qa_evidence_summary` and `candidate_browser_qa_evidence_rows`. This route-level reader summarizes ignored local `scripts/motion_browser_qa_runner.mjs` reports for `#candidates` only, including visual/performance pass state, review rows, report path, and no-provider/no-trade flags. It does not open a browser, write artifacts, commit screenshots, prove provider-backed parity, or mark `production_radar_replacement_complete`.
- `POST /api/candidate-radar/browser-qa-review` now creates a button-gated local review task for the `#candidates` ignored runner evidence. It records `candidate_browser_qa_review_contract` and rows, requires an explicit POST before `explicit_review_task_done=true`, and still keeps full-pool/deep-scan/provider-backed acceptance, legacy retirement, and production radar replacement blocked.
- On 2026-06-14, the explicit local browser runner completed default-motion and reduced-motion passes for the full LTG-14 route matrix; the Candidate Radar evidence reader found `#candidates` rows across desktop/laptop/tablet/mobile, and the button-gated Candidate Radar browser QA review reached `candidate_browser_qa_review_ready_local_artifact` with zero blocking review rows in the same local app session. This is local workstation evidence only: it does not promote browser artifacts to CI evidence, does not prove provider-backed parity, and does not mark `production_radar_replacement_complete=true`.
- On 2026-06-16, the LTG-13 activation and durable-evidence receipts were tightened so a ready `candidate_browser_qa_review_contract` clears only the local browser visual/performance review gap. Durable CI/release promotion, worker full-pool/deep-scan execution, provider-backed parity call ledger, optional DeepSeek model ledger, legacy retirement, and production promotion remain blocked.
- On 2026-06-16, the LTG-13 durable-evidence recipe now recognizes a ready `candidate_radar_legacy_retirement_review_receipt` as local review evidence. This clears only the `legacy_retirement_review_required` missing-evidence row after an explicit local review, while `legacy_retirement_ready=false`, `legacy_fallback_required=true`, worker/provider/model evidence, and production promotion remain blocked.
- On 2026-06-16, `POST /api/candidate-radar/production-promotion-review` now records a button-gated local production-promotion review receipt after the promotion dry-run and legacy-retirement review are visible. The durable-evidence recipe can clear only the `production_promotion_review_required` row from this local receipt; worker full-pool execution, worker deep-scan execution, provider-backed parity call ledger, optional DeepSeek model ledger, release/browser promotion, `legacy_retirement_ready`, and `production_radar_replacement_complete` remain blocked.
- Candidate Radar browser QA evidence now requires stricter motion/viewport coverage: default-motion must pass desktop/laptop/tablet/mobile and reduced-motion must also pass desktop/laptop/tablet/mobile before `candidate_browser_qa_evidence_passed_local_artifact` or `candidate_browser_qa_review_ready_local_artifact` can be treated as locally ready. Missing default or reduced-motion viewports stay visible as review gaps instead of being silently accepted.
- `scripts/candidate_radar_contract.py` is now part of the local push gate. It reads only local cache/service contracts and keeps cache GET, quick-scan task gating, full-pool plan, full-pool local receipt, deep-scan plan, deep-scan local review receipt, no-feature-loss QA, replacement-gap triage, promotion-blocker audit, result-delta clarity, candidate-priority explanation, no-provider, no-model, no-trade, and no-action boundaries auditable while `production_radar_replacement_complete=false` and `legacy_retirement_ready=false`.
- `scripts/candidate_radar_browser_qa_runbook.py` is now part of the local push gate after the LTG-13 contract and before generic motion QA. It is a static execution runbook only; it keeps `visual_qa_complete=false`, `browser_performance_trace_done=false`, `production_radar_replacement_complete=false`, and `legacy_retirement_ready=false`.
- Current 3.0 radar path is still not a full replacement for the legacy radar workflow.
- Runtime mode policy turns search-driven radar/quant projection into future mode-gated work: `cache_only` shows existing radar cache only, `manual` uses explicit scan/plan/review buttons, and future `live_light` may create a one-shot background task for a searched symbol or watchlist subset without starting full-market/deep scans on render.
- The Candidate Radar page now reads `GET /api/bootstrap/status` directly and displays the current runtime mode, `live_light` enablement, Tushare auto-refresh switch, DeepSeek pro auto-explanation switch, symbol/rate limits, bootstrap task skeleton status, provider/model execution flags, activation receipt status, mode rows, config rows, provider linkage rows, and bootstrap envelope ledger. This keeps next-ticket radar users aware of whether they are in `cache_only`, `manual`, or `live_light` without leaving the radar page; it is read-only and does not call Tushare/DeepSeek/GitHub or start full-pool/deep-scan from render.
- A button-gated local `run_candidate_radar_quant_projection` task now writes `search_quant_projection_receipt` and `search_quant_projection_rows` for a searched A-share symbol. It validates/infers the symbol suffix, shows the "生成 3.0 量化推演" path in React, and lists the missing Tushare light call ledger, Factor Quant Hub refresh, Next Session/ECharts cache refresh, optional DeepSeek pro model ledger, and freshness evidence. This is a local receipt only: it does not call Tushare, does not call DeepSeek, does not refresh Factor/Next Session/ECharts, does not start full-pool/deep-scan, and does not generate a buy/sell instruction.
- Candidate radar packets now expose `search_quant_projection_activation_receipt` and `search_quant_projection_activation_rows`: this local activation receipt turns the searched-symbol quant projection into a Tushare/DeepSeek linkage acceptance checklist. It keeps real Tushare light call ledger, optional DeepSeek pro model ledger, Factor/Next Session/ECharts refresh, browser non-blocking evidence, redaction review, and promotion review pending while confirming React render remains provider-silent and the projection remains research-only.
- `POST /api/candidate-radar/quant-projection-acceptance-dry-run` now creates a button-gated local dry-run for searched-symbol Tushare/DeepSeek linkage acceptance. It validates the symbol scope, caps Tushare APIs to `trade_cal / daily / daily_basic / moneyflow`, reports ignored APIs, checks only server-side credential presence without values or env key names, writes an `acceptance_scope_ticket`, and keeps Tushare/DeepSeek/GitHub calls false. It is a preflight receipt only: no provider/model execution, no Factor/Next/ECharts refresh, no browser runtime proof, no production promotion, and no trade/action mutation.
- `POST /api/candidate-radar/quant-projection-execution-request` now creates a button-gated local execution-request ticket for searched-symbol provider/model projection acceptance. It binds explicit operator approval, the latest `acceptance_scope_hash`, selected light APIs, future provider/model task route, no-secret boundary, no-trade boundary, and no-action-mutation boundary into `search_quant_projection_execution_request_receipt`. It keeps provider/model task creation, provider execution, model execution, Factor/Next/ECharts refresh, browser proof, production quant projection, and all Tushare/DeepSeek/GitHub calls false.
- `POST /api/candidate-radar/provider-parity-dry-run` now creates a button-gated local dry-run for broader next-ticket radar provider parity. It binds candidate symbols, selected legacy signal groups, future Tushare API scope, optional DeepSeek model-ledger requirement, server-side credential presence booleans, worker full-pool/deep-scan evidence, browser performance promotion, and no-trade/no-action boundaries into a `provider_parity_dry_run_receipt`. It does not call Tushare, does not call DeepSeek, does not run full-pool/deep-scan workers, does not retire the legacy radar fallback, and does not mark `production_radar_replacement_complete=true`.
- Candidate radar packets now expose `candidate_radar_worker_execution_recipe` and `candidate_radar_worker_execution_rows`: this local no-worker-start recipe turns the next full-pool/deep-scan production path into explicit future worker tasks, required storage datasets, required legacy signal groups, provider parity scope, browser promotion, and legacy-retirement gates. It keeps `worker_task_created=false`, `worker_execution_implemented=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `production_radar_replacement_complete=false`, and all provider/model/GitHub/trade flags false.
- `POST /api/candidate-radar/worker-execution-request` now creates a button-gated local worker execution-request ticket for the future next-ticket radar full-pool/deep-scan worker tasks. It binds explicit operator approval, the latest `candidate_radar_worker_execution_recipe.worker_execution_scope_hash`, local full-pool receipt visibility, local deep-scan review visibility, provider parity scope ticket visibility, optional searched-symbol quant projection scope ticket visibility, future worker routes, and no-worker/no-provider/no-model/no-trade/no-secret boundaries into `candidate_radar_worker_execution_request_receipt`. It keeps `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, and all Tushare/DeepSeek/GitHub/trade flags false.
- `POST /api/candidate-radar/full-pool-worker-scan` now creates a button-gated local `candidate_radar_full_pool_worker_fallback_receipt`. It consumes the local full-pool candidate universe through the worker-route shape after an approved worker execution-request hash, making the future full-pool worker path visible in React without starting Redis/Celery. This is still local fallback evidence only: `worker_started=false`, `celery_worker_started=false`, `redis_broker_used=false`, `production_full_pool_scan_done=false`, `provider_backed_acceptance_done=false`, `production_radar_replacement_complete=false`, and all Tushare/DeepSeek/GitHub/trade flags remain false.
- Candidate radar packets now expose `candidate_radar_durable_evidence_recipe` and rows: this local recipe fixes the remaining durable production evidence checklist across cache/render silence, quick-scan task pipeline, legacy parity, no-feature-loss surface, result-delta clarity, local full-pool/deep-scan receipts, worker execution recipe, provider parity scope ticket, searched-symbol quant projection scope ticket, worker full-pool/deep-scan evidence, provider-backed parity call ledger, browser visual/performance evidence, optional DeepSeek model ledger, legacy-retirement review, production promotion review, and no-trade/no-action/no-secret boundary. It keeps `durable_evidence_complete=false`, `durable_promotion_ready=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, and all Tushare/DeepSeek/GitHub/trade flags false.
- `scripts/candidate_radar_contract.py` now exposes `candidate_radar_production_stage_scope_manifest`: a local push-gate manifest for the remaining production-replacement stages. It keeps cache render, quick-scan task pipeline, local full-pool receipt, local deep-scan review, worker full-pool, worker deep-scan, provider parity, searched-symbol provider/model projection, browser visual/performance promotion, and legacy retirement review explicit while `production_radar_replacement_complete=false`.
- Candidate Radar cache and React now expose `candidate_radar_production_stage_scope_manifest` and rows directly on the page. This promotes the same remaining production-replacement stage list into the user-facing 3.0 radar surface: stage count, pending count, local evidence count, worker/provider/browser/CI blockers, no-trade/no-action flags, and no-provider/no-model/no-GitHub flags stay visible without starting worker tasks, full-pool scans, deep scans, Tushare, DeepSeek, GitHub, browser QA, or legacy retirement.
- Migration Status now observes the Candidate Radar stage-scope manifest from the local cache and surfaces it in the 14-LTG overview as `ltg_stage_scope_observed_rows`. This keeps LTG-13 visible from the global roadmap page, but the observed row is only local cache evidence; it does not close LTG-13, does not prove provider-backed parity, does not run worker full-pool/deep-scan, does not run browser QA, and does not call Tushare, DeepSeek, GitHub, or trading paths.
- `POST /api/candidate-radar/production-replacement-review` now creates a button-gated local production-replacement review receipt. It summarizes cache/render silence, quick-scan task pipeline, no-feature-loss and legacy parity evidence, local full-pool/deep-scan receipts, provider parity scope, worker execution request, searched-symbol quant projection request, local browser QA review, durable evidence recipe, and production stage scope manifest while keeping `ready_for_production_replacement=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, and `legacy_fallback_required=true`.
- `POST /api/candidate-radar/production-promotion-dry-run` now creates a button-gated local promotion dry-run. It binds explicit operator approval to the latest `candidate_radar_production_replacement_review_receipt.review_scope_hash`, records a new `candidate_radar_production_promotion_dry_run_receipt` and rows, and keeps direct worker full-pool/deep-scan evidence, provider-backed parity call ledger, optional DeepSeek model ledger, durable browser/CI evidence, legacy retirement, and production completion as blockers. It does not start Redis/Celery, does not call Tushare/DeepSeek/GitHub, does not run browser QA, does not retire Streamlit fallback, does not mutate `strategy action`, and does not mark `production_radar_replacement_complete=true`.
- `POST /api/candidate-radar/legacy-retirement-review` now creates a button-gated local legacy-retirement review receipt. It makes the old radar/Streamlit fallback retirement blocker auditable after production replacement review and promotion dry-run scope binding, while keeping real worker full-pool/deep-scan evidence, provider parity call ledger, optional DeepSeek model ledger, browser promotion, durable release evidence, `legacy_retirement_ready=false`, and `production_radar_replacement_complete=false`.
- Migration Status now observes the Candidate Radar production promotion dry-run receipt from the local cache and surfaces `observed_production_promotion_dry_run_*` fields on the LTG-13 row. React also shows those fields in a dedicated "LTG-13 下一票雷达 promotion dry-run" summary so the latest local ticket status, local-review state, blocker count, and cannot-close boundary are visible without searching the full table. This only makes the latest local promotion-ticket status visible in the 14-goal overview; `candidate_radar_production_promotion_dry_run_missing` or `ready_for_local_promotion_review=true` still cannot close LTG-13 without direct worker/provider/model/browser/legacy evidence.

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
- The fast-scan task-pipeline contract is local workflow evidence; it does not prove async worker execution, real provider/model refresh, browser performance, full-pool/deep-scan acceptance, legacy retirement, or production radar replacement.
- The full-pool local execution receipt is local universe execution evidence; it does not prove provider-backed full-market acceptance, production worker execution, browser QA, Streamlit retirement, or trading readiness.
- The deep-scan local review receipt is local candidate-evidence review evidence; it does not prove model-backed deep research, provider-backed acceptance, production worker execution, browser QA, Streamlit retirement, or trading readiness.
- The Candidate Radar production activation receipt is a local next-step checklist; it does not execute worker scans, call providers/models, promote browser artifacts, create CI evidence, retire the legacy radar, or prove full replacement.
- The Candidate Radar legacy parity acceptance receipt is local no-feature-loss gating; it blocks treating `gap_reported` as feature parity, blocks retiring the Streamlit radar fallback before provider/worker/browser acceptance, and still does not execute scans, call providers/models, run browser QA, or prove production replacement.
- The result-delta clarity contract is local QA; previous-cache diff is only complete when a prior persisted radar packet exists, and it still does not prove browser visual QA or production radar replacement.
- The candidate-priority explanation contract is local QA; it explains current cache ordering and evidence gaps only. It does not sort, rescore, calculate action, refresh data, or prove provider-backed full-pool/deep-scan acceptance.
- The Candidate Radar browser QA runbook is ready, but it is still a static plan; it does not prove the browser pass ran, and ignored local screenshots/reports are not durable CI or production acceptance.
- The Candidate Radar browser QA evidence reader can make local ignored `#candidates` report evidence visible, but local reports are still workstation artifacts, not durable CI proof, not provider-backed acceptance, and not full radar replacement.
- The Candidate Radar browser QA review task is now button-gated and local-only, but it still reviews ignored local artifacts rather than running browser QA in CI or proving provider-backed parity.
- The Candidate Radar durable evidence recipe is local checklist evidence only; it does not create provider parity scope tickets, execute worker full-pool/deep-scan tasks, produce provider call ledgers, run DeepSeek, promote browser visual/performance artifacts, retire legacy radar fallback, or prove production replacement.
- The Candidate Radar legacy retirement review receipt is local review evidence only. It can clear the durable checklist's "legacy retirement review required" row after explicit approval, but it still cannot retire Streamlit fallback, mark `legacy_retirement_ready=true`, or close LTG-13 without worker/provider/model/browser promotion and a production promotion review.
- The Candidate Radar production promotion review receipt is local review evidence only. It can clear the durable checklist's "production promotion review required" row after explicit approval, but it still cannot mark production replacement complete, retire legacy fallback, create worker/provider/model/browser evidence, or allow render-time Tushare/DeepSeek/GitHub calls.
- The Candidate Radar production-replacement review receipt is a local roll-up review only. Even when `local_review_ready=true`, it must keep direct worker execution, provider-backed parity, durable browser promotion, legacy retirement, and production promotion as blockers until those direct evidence items exist.
- The Candidate Radar production promotion dry-run is a scope-binding ticket only. Even when `ready_for_local_promotion_review=true`, it still does not run worker/provider/model/browser work, does not promote durable evidence, does not retire the legacy radar, and does not complete production replacement.
- The Migration Status LTG-13 promotion dry-run observation is a dashboard field only. It mirrors the local receipt status and blocker count, but does not create a task, execute a task, call providers/models, promote evidence, or close the goal.
- A single default-motion browser pass is no longer sufficient local evidence; reduced-motion and all four target viewports must also be present before the browser QA evidence/review status can become locally ready.
- The local Candidate Radar push-gate contract is not a production radar run; it only blocks regressions where local quick scans, plan-only rows, provider parity dry-run rows, no-feature-loss QA, replacement triage, promotion-blocker audit, result-delta clarity, or candidate-priority explanation could be mistaken for full replacement.
- `fast_scan_local_ready_full_pool_pending` is not production replacement; it only proves local readiness and visible gaps.
- Need parity acceptance before removing any Streamlit fallback.
- Need provider/model-backed search-to-quant projection beyond the current local receipt: validate the symbol, refresh allowed light data, write real call ledger/model ledger, update factor and next-session cache, and render chart/provenance without reducing legacy radar signal coverage.
- Need the activation receipt to be followed by a separate user-approved real provider/model task before claiming Tushare/DeepSeek linkage completion; the receipt itself is only a local checklist and does not prove provider/model execution.
- Need the acceptance dry-run to be followed by a separate real provider/model implementation bound to the `acceptance_scope_ticket`; dry-run readiness, credential presence, and ignored-API reporting do not prove real Tushare rows or DeepSeek JSON stability.
- Need the quant projection execution-request ticket to be followed by a separate real provider/model task implementation bound to the latest `acceptance_scope_hash`; `search_quant_projection_execution_request_receipt.local_execution_request_ready=true` only proves approval/scope binding and does not create a provider/model task, call Tushare/DeepSeek/GitHub, refresh Factor/Next/ECharts, or complete production quant projection.
- Need the provider parity dry-run to be followed by a separate real provider/model/worker/browser implementation bound to the `provider_parity_dry_run_receipt`; candidate scope, credential presence, selected signal groups, and scope hash do not prove real Tushare rows, DeepSeek JSON stability, full-pool/deep-scan execution, browser performance promotion, or legacy fallback retirement.
- Need the worker execution recipe to be followed by real worker task implementation and evidence. `candidate_radar_worker_execution_recipe.local_worker_execution_recipe_ready=true` only means the future full-pool/deep-scan worker path is visible; it does not create a worker task, start Redis/Celery, read provider data, call DeepSeek, write production scan evidence, or retire the legacy radar fallback.
- Need the worker execution-request ticket to be followed by separate real worker task implementation and evidence. `candidate_radar_worker_execution_request_receipt.local_execution_request_ready=true` only means approval and scope are bound to the current worker recipe plus local evidence tickets; it does not create a worker task, start Redis/Celery, run full-pool/deep-scan, call Tushare/DeepSeek/GitHub, write production scan evidence, or retire the legacy radar fallback.
- Need the full-pool worker fallback route to be followed by separate real Celery/Redis worker execution and provider-backed parity evidence. `candidate_radar_full_pool_worker_fallback_receipt.local_worker_fallback_full_pool_done=true` only means a button-gated local fallback consumed local candidates through the worker route shape; it does not create a worker task, start Redis/Celery, run provider-backed full-pool scanning, call Tushare/DeepSeek/GitHub, promote browser evidence, or retire the legacy radar fallback.
- Need the deep-scan worker fallback route to be followed by separate real Celery/Redis worker execution, DeepSeek/model ledger evidence if enabled, and provider-backed parity evidence. `candidate_radar_deep_scan_worker_fallback_receipt.local_worker_fallback_deep_scan_done=true` only means a button-gated local fallback consumed local deep-scan review evidence through the worker route shape; it does not create a worker task, start Redis/Celery, call DeepSeek, run provider-backed deep research, call Tushare/GitHub, promote browser evidence, or retire the legacy radar fallback.
- Need explicit intraday-provider strategy before adding any realtime market state: every non-Tushare source must have provider identity, call ledger, freshness, mode gating, and safe-error status.
- The production stage-scope manifest is a pending checklist, not execution evidence. It does not run worker full-pool, worker deep-scan, provider parity, model explanation, browser promotion, durable release evidence, or legacy retirement.

### Implementation Phases

1. Inventory legacy radar inputs, scoring fields, filters, exclusions, and output packet shape.
2. Build a fast local scan task that reads existing cache/storage first and returns a task receipt immediately.
3. Add progressive scan modes: `quick_cache_scan`, `watchlist_scan`, `custom_pool_scan`, `full_pool_plan`, `deep_scan_plan`, and later real `full_pool_scan` / `deep_scan`.
4. Add coverage metrics so the UI shows what was scanned, skipped, stale, or blocked.
5. Preserve signal parity before removing any legacy fallback.
6. Move slow provider refreshes behind explicit POST tasks instead of radar page render.
7. Add future search-driven "生成 3.0 量化推演" / "一键生成量化投研图谱" task for a single symbol or bounded watchlist subset.
8. Allow `live_light` radar/quant bootstrap only after cache render, with symbol limit, rate limit, task dedupe, and visible skipped state.
9. Preserve the legacy next-ticket radar signal groups before retiring fallback: Top / Watch / Excluded split, evidence links, scoring dimensions, trigger / invalidation logic, holding comparison, candidate pool sources, scan filters, timeout fallback, manual deep research path, and output fields.
10. Promote the local fast-scan task pipeline to real worker-backed execution only after task status, last-cache fallback, safe failure, provider/freshness gaps, browser performance, and no-feature-loss evidence are all accepted.
11. Generate a scope-bound worker execution-request ticket before any future radar worker task is submitted.
12. Generate a scope-bound searched-symbol provider/model execution-request ticket before any future quant projection provider/model task is submitted.
13. Keep the production stage-scope manifest current whenever worker, provider/model, browser promotion, or legacy-retirement evidence changes.

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
- Search-to-quant projection validates the symbol, refreshes allowed light data, writes call ledger/model ledger, refreshes factor and next-session cache, builds ECharts payload, and shows task progress, provenance, freshness, factor support/suppress/neutral/missing, DeepSeek state, and chart results.
- Candidate Radar page must show the active runtime mode and `live_light` bootstrap boundaries from `GET /api/bootstrap/status`: current mode, Tushare auto-refresh on/off, DeepSeek pro auto-explanation on/off, symbol/rate limits, task skeleton status, provider/model execution pending flags, activation receipt, provider linkage rows, and bootstrap call ledger. This visibility does not permit render-time provider/model calls or full-pool/deep-scan startup.
- Current search-to-quant projection local receipt validates the symbol, writes receipt rows, exposes missing provider/model/factor/chart evidence, and keeps `ready_for_real_provider_model_projection=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, and `production_quant_projection_complete=false`.
- `search_quant_projection_activation_receipt.local_activation_receipt_ready=true` only means the next Tushare/DeepSeek linkage acceptance path is visible: explicit provider/model task, real Tushare call ledger, optional DeepSeek model ledger, Factor/Next/ECharts refresh evidence, browser non-blocking evidence, redaction review, and production promotion review. It must keep `ready_for_real_provider_model_projection=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, and `production_quant_projection_complete=false`.
- `search_quant_projection_acceptance_dry_run_receipt.local_dry_run_ready=true` only means the local preflight is reviewable: explicit approval, symbol scope, allowed APIs, credential-presence booleans, scope hash, and no-secret boundaries are visible. It must keep `ready_to_execute_real_provider_model_task=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, and `production_quant_projection_complete=false`.
- `search_quant_projection_execution_request_receipt.local_execution_request_ready=true` only means an explicit POST has bound operator approval and the latest acceptance dry-run scope hash to the future searched-symbol provider/model task. It must keep `provider_model_task_created=false`, `provider_model_task_dispatched=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, `tushare_called=false`, `deepseek_called=false`, `github_called=false`, `factor_refresh_executed=false`, `next_session_refresh_executed=false`, `echarts_payload_refreshed=false`, `production_quant_projection_complete=false`, no real trades, and no `strategy action` mutation.
- The 3.0 radar replacement cannot drop legacy radar functions silently; missing or degraded legacy signal coverage must appear as explicit coverage gaps.
- `no_feature_loss_acceptance_contract.local_no_feature_loss_contract_ready=true` only means the local QA surface is visible; `production_radar_replacement_complete` remains false until browser performance, real full-pool/deep-scan execution, and provider-backed parity acceptance are complete.
- `replacement_gap_triage_contract.local_triage_ready=true` only means blockers to retiring the legacy radar are classified and visible; `legacy_retirement_ready` must remain false while critical/provider/freshness/browser/performance/full-pool/deep-scan/provider-backed gaps remain.
- `quick_scan_execution_receipt.local_quick_scan_receipt_ready=true` only means the local cache/quick/watchlist/custom execution receipt and its gaps are visible. It must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false` until direct production evidence exists.
- `fast_scan_task_pipeline_contract.local_task_pipeline_ready=true` only means the local cache-first / POST-task / status-panel / previous-cache / safe-failure / budget / gap-visibility workflow is reviewable. It must keep `async_worker_execution_done=false`, `provider_backed_acceptance_done=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, and `deep_scan_done=false` until direct worker/provider/browser evidence exists.
- `candidate_radar_production_activation_receipt.local_activation_receipt_ready=true` only means the next safe acceptance path is clear: explicit worker full-pool/deep-scan execution, provider-backed parity, browser visual/performance review, durable evidence, and legacy-retirement review. It must keep production completion flags false until those direct evidence items exist.
- `candidate_radar_worker_execution_recipe.local_worker_execution_recipe_ready=true` only means the future worker path is scoped and reviewable. It must keep `ready_to_start_worker_from_cache=false`, `worker_task_created=false`, `worker_execution_implemented=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `page_render_starts_worker=false`, and no Tushare/DeepSeek/GitHub calls.
- `candidate_radar_worker_execution_request_receipt.local_execution_request_ready=true` only means an explicit POST has bound operator approval and the latest worker recipe scope hash to existing local full-pool/deep-scan/provider-parity evidence tickets. It must keep `worker_task_created=false`, `worker_task_executed=false`, `worker_started=false`, `worker_execution_implemented=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, no Tushare/DeepSeek/GitHub calls, no real trades, and no `strategy action` mutation.
- `full_pool_local_execution_receipt.local_full_pool_execution_done=true` only means a button-gated local universe task consumed local rows and wrote a receipt. It must keep `production_full_pool_scan_done=false`, `provider_backed_acceptance_done=false`, `worker_backed_execution_done=false`, `legacy_retirement_ready=false`, and `legacy_fallback_required=true`.
- `deep_scan_local_review_receipt.local_deep_scan_review_done=true` only means a button-gated local review task inspected existing candidate evidence and gaps. It must keep `deep_scan_done=false`, `deep_scan_validation_done=false`, `provider_backed_acceptance_done=false`, `deepseek_called=false`, `worker_backed_execution_done=false`, `legacy_retirement_ready=false`, and `legacy_fallback_required=true`.
- `candidate_radar_deep_scan_worker_fallback_receipt.local_worker_fallback_deep_scan_done=true` only means a button-gated local route consumed the existing deep-scan review and approved worker execution-request scope. It must keep `production_deep_scan_done=false`, `deep_scan_done=false`, `worker_deep_scan_execution_done=false`, `worker_started=false`, `redis_broker_used=false`, `celery_worker_started=false`, `provider_backed_acceptance_done=false`, `model_execution_implemented=false`, `deepseek_model_execution_done=false`, `deepseek_model_ledger_complete=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, no Tushare/DeepSeek/GitHub calls, no real trades, and no `strategy action` mutation.
- `legacy_parity_acceptance_receipt.local_acceptance_receipt_ready=true` only means the old radar's no-feature-loss checklist is visible and locally guarded. It must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `legacy_fallback_required=true`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false` until worker execution, provider-backed parity, and browser visual/performance acceptance are complete.
- `production_radar_replacement_complete` remains false until real full-pool/deep-scan execution and provider-backed parity acceptance are complete.
- `result_delta_clarity_contract.local_result_delta_clarity_ready=true` means result-change cues are visible; `previous_cache_diff_done=true` is allowed only after comparing against a previous persisted radar packet, while `browser_visual_delta_qa_done=false` must remain explicit until browser visual QA is run.
- `candidate_browser_qa_runbook_contract.local_runbook_ready=true` only means the `#candidates` browser QA route/viewports/criteria are pinned; `visual_qa_complete` and `browser_performance_trace_done` remain false until an explicit browser run is reviewed.
- `candidate_browser_qa_evidence_summary.local_browser_qa_evidence_found=true` only means a local ignored runner report for `#candidates` was summarized. Even when `candidate_visual_qa_evidence_passed=true` and `candidate_browser_performance_evidence_passed=true`, `production_radar_replacement_complete=false` and `legacy_retirement_ready=false` must remain until real full-pool/deep-scan execution and provider-backed parity acceptance are complete.
- `candidate_browser_qa_review_contract.local_browser_qa_review_ready=true` is allowed only after explicit POST review and complete local default/reduced-motion evidence, and still must keep `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, and `provider_backed_acceptance_done=false`.
- A passing local Candidate Radar browser QA review must include both default-motion and reduced-motion `#candidates` evidence across desktop/laptop/tablet/mobile, zero review-required rows, no external/model/provider calls, no trade execution, and no mutation of `strategy action`.
- `scripts/candidate_radar_contract.py` passes in the push gate while still reporting `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `browser_performance_trace_done=false`, and `browser_visual_delta_qa_done=false`.
- `candidate_radar_production_stage_scope_manifest` contains all required production stages and every row keeps `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `full_pool_scan_done=false`, `deep_scan_done=false`, `provider_backed_acceptance_done=false`, `worker_backed_execution_done=false`, `browser_performance_trace_done=false`, `browser_visual_delta_qa_done=false`, `provider_execution_implemented=false`, `model_execution_implemented=false`, `page_render_starts_full_pool=false`, `page_render_starts_deep_scan=false`, `candidate_is_not_buy_instruction=true`, and no external/model/provider/GitHub calls.
- `candidate_radar_production_replacement_review_receipt.local_review_ready=true` may only mean the local evidence roll-up is reviewable. It must keep `ready_for_production_replacement=false`, `production_radar_replacement_complete=false`, `legacy_retirement_ready=false`, `legacy_fallback_required=true`, `worker_full_pool_done=false`, `worker_deep_scan_done=false`, `provider_backed_parity_done=false`, `browser_visual_performance_promoted=false`, no Tushare/DeepSeek/GitHub calls, no real trades, and no `strategy action` mutation.
- Radar output does not become a buy instruction and does not modify `strategy action`.
- Future search-to-quant projection returns task progress, data source provenance, call ledger, factor support/suppress/neutral/missing rows, freshness status, DeepSeek status, and chart payload without calculating trade action in React.
- Future `live_light` radar/quant bootstrap is bounded to current target / current holdings / watchlist subset; full-pool and deep-scan execution remain explicit worker tasks and never page-render side effects.

### Forbidden

- Do not scan the full market on page load.
- Do not start full-pool or deep-scan execution from `live_light` page open; only bounded light bootstrap may be considered after opt-in.
- Do not treat a search-to-quant projection result as a buy/sell recommendation.
- Do not treat `search_quant_projection_receipt` as real Tushare refresh, DeepSeek execution, Factor/Next Session refresh, ECharts payload refresh, browser non-blocking evidence, production quant projection, or a buy/sell recommendation.
- Do not treat `search_quant_projection_activation_receipt` as real Tushare/DeepSeek linkage completion, provider-backed quant projection, browser non-blocking acceptance, production promotion, or permission to call Tushare/DeepSeek from React render.
- Do not treat `search_quant_projection_acceptance_dry_run_receipt` as provider/model execution, production quant projection, DeepSeek JSON stability proof, real Tushare sample evidence, or permission to expose env key names / credential values.
- Do not treat `search_quant_projection_execution_request_receipt` as provider/model task creation, Tushare execution, DeepSeek execution, Factor/Next/ECharts refresh, browser proof, production quant projection, or a buy/sell recommendation.
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
- Do not treat `fast_scan_task_pipeline_contract` as async worker execution, provider-backed parity, browser performance proof, full-pool scan completion, deep-scan completion, legacy retirement readiness, or production radar replacement.
- Do not treat `candidate_radar_production_activation_receipt` as production replacement, worker execution, provider-backed parity, durable browser/CI evidence, legacy retirement readiness, or a buy-signal approval.
- Do not treat `candidate_radar_worker_execution_recipe` as worker execution, full-pool scan completion, deep-scan completion, provider-backed parity, browser promotion, production replacement, or legacy fallback retirement.
- Do not treat `candidate_radar_worker_execution_request_receipt` as worker execution, worker task creation, full-pool scan completion, deep-scan completion, provider-backed parity, DeepSeek/model execution, browser promotion, production replacement, or legacy fallback retirement.
- Do not treat `candidate_radar_deep_scan_worker_fallback_receipt` as worker execution, worker task creation, deep-scan completion, DeepSeek/model execution, provider-backed parity, browser promotion, production replacement, or legacy fallback retirement.
- Do not treat `result_delta_clarity_contract` as browser visual QA or production radar replacement. Do not treat previous-cache diff as complete unless `previous_cache_diff_done=true` and `previous_cache_diff_rows` are present.
- Do not treat `candidate_browser_qa_evidence_summary` as CI evidence, provider-backed parity, legacy retirement readiness, or production radar replacement.
- Do not treat `candidate_browser_qa_review_contract` as browser execution, CI evidence, provider-backed parity, legacy retirement readiness, or production radar replacement.
- Do not treat `scripts/candidate_radar_contract.py` passing as full-pool scan, deep scan, provider-backed parity acceptance, browser performance proof, visual QA, legacy retirement readiness, or production radar replacement.
- Do not treat `candidate_radar_production_stage_scope_manifest` as worker execution, provider/model execution, browser promotion, durable evidence, legacy retirement approval, or production radar replacement.
- Do not treat `candidate_radar_production_replacement_review_receipt` as worker execution, provider-backed parity, browser promotion, durable CI evidence, legacy retirement approval, Streamlit fallback removal, or production radar replacement.
- Do not treat `candidate_radar_production_promotion_dry_run_receipt` as production radar replacement, worker/provider/model/browser execution, durable evidence promotion, legacy retirement approval, Streamlit fallback removal, or permission to call Tushare/DeepSeek/GitHub from render.
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
- Visual hierarchy surfaces now add a finite `cc-keynote-focus-sweep` cue: the cue sits behind card content, respects reduced-motion, and is guarded by `keynote_focus_sweep_cue` in the local static audit so polish remains clarity-first rather than decorative or trade-urgent.
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
- `POST /api/audit/motion-production-promotion-dry-run` now creates a button-gated LTG-14 promotion dry-run. It reads the local audit cache plus ignored motion QA summaries, binds the reviewed local artifact, visual promotion scope, performance promotion scope, and durable CI/release evidence gap into `motion_promotion_dry_run_receipt` and rows, and still keeps `production_motion_complete=false`, `browser_visual_qa_promoted=false`, `browser_performance_promoted=false`, and `ci_evidence_complete=false`.
- On 2026-06-14, the explicit local browser runner completed two local passes after manual FastAPI/Vite startup: default motion passed 20/20 route-viewport rows with zero console errors, and reduced-motion passed 20/20 route-viewport rows with zero console errors. The button-gated Motion browser QA review reached `motion_browser_qa_review_ready_local_artifact` with zero blocking review rows in the same local app session. These reports are local ignored artifacts and still require durable review/promotion before production completion claims.
- Mobile layout now has a responsive breakpoint so navigation no longer squeezes Command Center content or state clarity rails on narrow screens. Local default-motion and reduced-motion browser runner reports can prove a specific run, but ignored local artifacts are not durable CI or production motion completion.
- `scripts/motion_viewport_qa_contract.py` now exposes `motion_production_stage_scope_manifest`: a local static manifest for the remaining production-motion path. It tracks motion source guardrails, state-change confirmation cues, chart/radar delta choreography, reduced-motion review, viewport visual QA, browser performance trace, local artifact review, durable CI/release evidence, production promotion review, and no-trade/no-action boundaries while keeping `production_motion_complete=false`.
- Call Ledger Audit now exposes `motion_durable_evidence_recipe` and `motion_durable_evidence_rows`: this LTG-14 recipe maps local ignored browser reports, button-gated review, promotion dry-run scope, default/reduced-motion coverage, durable visual evidence, browser performance trace, durable CI/release evidence, artifact redaction, and no-provider/no-model/no-trade boundaries into one checklist. It keeps `production_motion_complete=false`, `browser_visual_qa_promoted=false`, `browser_performance_promoted=false`, `ci_evidence_complete=false`, and `durable_ci_evidence_complete=false`.
- Migration Status now observes the LTG-14 `motion_production_stage_scope_manifest` from the local static motion contract and surfaces it in `ltg_stage_scope_observed_rows` beside LTG-13. React also shows those fields in a dedicated "LTG-14 动效生产证据" summary so motion stage scope, pending count, local evidence rows, visual QA promotion, performance promotion, durable CI evidence, and production motion status are visible without searching the full table. This makes the global 14-LTG page show motion stage count, pending count, local source evidence count, visual/performance/CI blockers, and no-provider/no-model/no-trade boundaries without opening a browser, writing QA artifacts, calling GitHub, calling Tushare/DeepSeek, mutating packet values, or completing production motion.
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
- `motion_promotion_dry_run_ready_production_still_blocked` means local reviewed evidence and promotion scope are bound for human review; it still does not promote visual/performance evidence, verify remote CI, call GitHub, or complete production motion.
- The production stage-scope manifest is a local pending checklist. It does not execute browser QA, promote local ignored artifacts, prove reduced-motion browser behavior, create durable release evidence, or mark production motion complete.
- The durable evidence recipe is a local gap map, not execution evidence. It does not inspect GitHub Actions, run browser QA, promote visual/performance artifacts, or make local ignored reports durable.

### Implementation Phases

1. Define a restrained motion system inspired by high-end product keynotes: clear staging, smooth state changes, and low visual noise.
2. Add motion tokens for duration, easing, delay, opacity, transform, and chart update transitions.
3. Apply motion first to task progress, cache refresh, page transitions, ECharts updates, and candidate-radar scan results.
4. Add reduced-motion fallbacks and performance checks.
5. Verify desktop and mobile viewports so animation does not overlap, occlude, or resize critical text.
6. Keep the production stage-scope manifest current whenever local visual evidence, performance evidence, durable release evidence, or production promotion status changes.

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
- `motion_promotion_dry_run_receipt.ready_for_local_promotion_review=true` only means the local promotion scope is bound after explicit approval and reviewed local evidence; `ready_to_mark_production_motion_complete`, `browser_visual_qa_promoted`, `browser_performance_promoted`, `ci_evidence_complete`, and `production_motion_complete` must remain false until a separate durable promotion step exists.
- `motion_durable_evidence_recipe.local_recipe_ready=true` only means the durable evidence path is explicit. It must still keep `ready_to_mark_production_motion_complete=false`, `browser_visual_qa_promoted=false`, `browser_performance_promoted=false`, `ci_evidence_complete=false`, `durable_ci_evidence_complete=false`, and `production_motion_complete=false` until a separate promotion step attaches durable visual, performance, reduced-motion, and CI/release evidence.
- `motion_clarity_audit.static_ready=true` is allowed only when static source checks pass.
- `motion_production_stage_scope_manifest` contains every required production-motion stage and each row keeps `production_motion_complete=false`, `visual_qa_complete=false`, `browser_performance_verified=false`, `browser_visual_qa_promoted=false`, `browser_performance_promoted=false`, `durable_ci_evidence_complete=false`, `browser_runner_executed_by_contract=false`, `local_artifact_reviewed_for_production=false`, `changes_packet_values=false`, `changes_strategy_action=false`, `changes_price_or_position=false`, no external/model/provider/GitHub calls, and no trade execution.
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
- Do not treat `motion_promotion_dry_run_receipt` as browser execution, GitHub Actions proof, durable CI evidence, visual QA promotion, performance promotion, or production motion completion.
- Do not treat `motion_production_stage_scope_manifest` as browser execution, reduced-motion browser proof, visual/performance promotion, durable release evidence, or production motion completion.
- Do not treat `motion_durable_evidence_recipe` as browser execution, GitHub Actions proof, durable visual/performance evidence, reduced-motion proof, promotion approval, or production motion completion.

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
- 评审 Tushare / DeepSeek 联动时必须分清四层：初始 render 是否安静、是否创建 POST task、task 内是否真实调用 provider/model、是否具备生产验收 ledger；`GET /api/migration/status` 会用 `tushare_deepseek_mode_layer_rows` 固定这四层，而不是用一句绝对禁止或全部允许概括。
- POST task / worker / local fallback 才可能外部调用，且必须有模式、按钮或显式 payload 门控。
- `manual` 模式只允许用户点击按钮或提交显式任务后外联。
- `live_light` 模式可以在初始 cache render 后创建一次限频后台 bootstrap task，用于轻量 Tushare 刷新和可选 DeepSeek pro 解释；这不是 render 直接外联。
- `live_light` 默认关闭，必须可配置、可见、可审计、可跳过、可失败降级。
- `live_light` 的 Tushare 自动刷新只允许在 POST task 内执行轻量范围：`trade_cal` when needed、`daily`、`daily_basic`、`moneyflow`，默认只覆盖当前标的/持仓/watchlist/搜索标的并受 symbol limit 与 rate limit 约束。
- `live_light` 的 DeepSeek pro 自动解释只允许在 Tushare / factor / next-session cache 准备好之后由 task 触发，必须使用 input hash 去重、model ledger、六字段 sanitizer、parse-failed 安全回退，并且不得覆盖数值、持仓、价格、`operation_zones` 或 `strategy action`。
- `live_full` 预留；全池/深扫不默认启用。
- GitHub probe 不进入 `live_light` 默认启动链路；仍需独立按钮或显式 task mode。
- DeepSeek 不作为数据源。
- Factor 分数不直接改 `strategy action`。
- 下一票雷达不在页面启动时做全市场扫描；`live_light` 只能覆盖当前标的/持仓/watchlist 的有界轻量任务。
- 盘中实时信息若使用非 Tushare provider，必须显示 provider 标识、freshness、call ledger、模式门控和 safe error，不允许无标识混用数据源。
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
- When discussing startup external calls, always name the layer: cache GET / initial React render, POST task creation, provider/model execution inside the task, or production promotion evidence.
- Do not revive the old flat wording "page startup never automates anything" once `live_light` is in scope; the correct baseline is `cache_only` default-deny plus explicit `manual` / `live_light` upgrades.
- Do not blur `live_light` into hidden automation: it must remain visible in UI, rate-limited, deduped, task-ledgered, safe to fail, non-blocking, and unable to mutate trading actions.
- Keep commit messages narrow and tied to one goal whenever possible.
