# Codex Handoff Protocol

This project uses a fixed handoff loop for ChatGPT-guided development:

ChatGPT designs task
-> User pastes task to Codex
-> Codex executes, validates, and either commits or returns a checkpoint
-> Codex returns CHATGPT_HANDOFF or Checkpoint
-> User pastes the returned report to ChatGPT when another planning pass is needed
-> ChatGPT designs next task

## Operating Rules

- The user should not manually run git, tests, py_compile, or smoke checks.
- Codex owns the local execution loop: inspect, edit, validate, and either commit or checkpoint according to scope.
- Implementation tasks may become commits after successful validation when the scope is clean. Checkpoint-only docs/config/runtime-mode wording cycles report evidence without forcing a commit unless the user explicitly asks for one.
- Codex does not push by default.
- Each round should be a small, reversible patch.
- Migration-strategy, docs/config, or runtime-mode wording cycles must stay bounded to at most one main target and one supporting target, modify no more than five files, and end with a `Checkpoint` that states the evidence boundary.
- Legacy parity means preserving useful user capabilities, data sources, signals, evidence chains, and research workflows; it does not mean copying legacy UI, navigation, bugs, historical patchwork, or confusing old workflows.
- Before any legacy Streamlit workflow is promoted into an ordinary React/Tauri path, the round must name its Legacy Bug / UX Audit classification (`KEEP`, `REDESIGN`, `LEGACY-DEBUG`, or `RETIRE`) and keep known bugs, confusing UX, historical patchwork, or unclear data lineage out of ordinary workflow code.
- Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests unless the round names the current release blocker they directly reduce.
- Strategy, docs, config, scaffold, preflight, local receipt, matrix, mock, or sanitizer rounds must not claim an LTG is complete; only direct acceptance evidence can support an LTG closeout claim.
- When a round is commit-scoped, one task should usually become one coherent commit.
- If a task spans unrelated concerns, split it into separate commits.

## stock-MING Safety Boundary

- Runtime automation is mode-layered, not an absolute startup ban.
- `cache_only` is the default: page open, React render, FastAPI startup, and GET cache/status routes stay read-only and never call providers, models, workers, or trading paths.
- `manual` allows external work only through an explicit user button or POST task.
- `live_light` may create or reuse one bounded local background POST task after cache render, but provider/model work must still go through the task contract, ledgers, redaction, and local fallback/worker boundary.
- `live_full` is reserved and default-off; it requires separate authorization before any full-pool, deep-scan, or broad automatic provider/model work can be enabled.
- Any permitted provider/model external work must produce redacted `call_ledger` / `model_ledger` rows before it can be described as real external evidence; missing ledger rows keep the result local or pending and cannot promote `live_light`, LTG completion, or production acceptance.
- Provider/model handoff reports must use safe summaries only: do not paste raw prompts, raw model output, unredacted provider errors, credential-like values, or raw packet bodies into checkpoints; model content may be reported only as whitelisted fields with `model_ledger` status and redaction review.
- Configured source switches, release switches, or `configured=true` rows are operator intent, not effective external calls. They become effective only after the current runtime mode, task gate, ledgers, redaction, and promotion rules allow them; `cache_only` forces effective automation false, `manual` remains explicit-button/POST only, `live_light` remains bounded local task creation after cache render, and `live_full` remains reserved with no hidden automation.
- Full backtests, full-market scans, heavy Tushare/AkShare/yfinance/Supabase refreshes, and any real trading path remain explicit-button or separately authorized work; they must not run from page open, render, GET cache/status, or search typing.
- DeepSeek is never a data source and must not overwrite prices, holdings, factors, operation zones, or strategy action.
- DeepSeek text, model summaries, or explanation status cannot satisfy missing evidence, cannot become a next-click action, and cannot replace provider/cache/factor/operation-zone evidence; they may only explain existing evidence with `model_ledger` status and redaction state.
- The legacy workspace must remain reachable unless a task explicitly changes that.
- Streamlit stays fallback / legacy / admin / debug until the React/Tauri ordinary entrances are demonstrably easier, clearer, and more reliable; do not describe Streamlit as the primary 3.0 runtime surface or target UX in a handoff or checkpoint.
- Service layers should remain UI-free.
- UI layers should consume packet-like data from services.
- Packets should stay JSON-friendly where possible.

## End-of-Round Report

Every Codex round should end with a `CHATGPT_HANDOFF` report, or a concise `Checkpoint` when the user explicitly requests checkpoint-style cycle reporting, that includes:

- Summary of what changed.
- Commit hash and message when committed, or explicit no-commit checkpoint status.
- Changed file list.
- Validation results.
- Diff stat or commit summary.
- Risk notes.
- Cycle scope: main target, supporting target, changed file count, and whether the round stayed inside the one-main / one-support / five-file cap.
- Migration checkpoint answers:
  - What user capability was preserved.
  - What legacy UX problem was removed.
  - Which legacy bug or patchwork path was intentionally not migrated.
  - What became simpler for a non-technical user.
  - Which real blocker was reduced.
- Production-evidence boundary: state whether the round is docs/config/scaffold/preflight/local receipt evidence or real production acceptance evidence.
- Legacy audit promotion gate: when a round touches legacy workflow migration or ordinary entrance placement, state whether any module was promoted to `KEEP`; if yes, cite direct Legacy Bug / UX Audit evidence for observed user action/workflow problem, removed legacy bug/confusing UX/patchwork path, data-lineage check, replacement ordinary entrance, and frozen legacy path.
- Legacy direct-evidence intake: when a round advances the first Legacy Bug / UX Audit pass, report the intake slots `user_observation`, `legacy_ux_bug_or_patchwork`, `data_lineage_observation`, `replacement_user_path`, `frozen_legacy_path`, `evidence_attachment`, and `keep_promotion_decision`; if the round only defines or fills first-pass intake, `keep_promotion_decision` must stay `no_keep_promotion_this_round`, and seed inventory, route inventory, local receipts, no-feature-loss matrix, mock, sanitizer, docs/config scaffold, or checklist wording must not be described as direct UX/bug evidence.
- Legacy evidence attachment safety: `evidence_attachment` must be a safe screenshot reference, redacted reviewer note, or safe log summary; never paste raw packet bodies, raw logs, token/key/credential values, unredacted model output, or generated artifacts into the checkpoint as direct UX/bug evidence.
- Runtime-mode boundary: state whether `cache_only`, `manual`, `live_light`, or reserved `live_full` behavior changed, and confirm GET/cache/render/startup/search typing stayed silent unless explicitly changed and validated.
- Runtime policy row boundary: when a round touches config, bootstrap status, runtime contracts, or shared UI/operator mode sources, state whether `runtime_mode_policy_rows` still expose `cache_get_rule`, `react_render_rule`, `ledger_rule`, `ordinary_entrance_visibility_rule`, `ordinary_mode_banner_rule`, `configured_switch_rule`, `effective_external_call_rule`, and `production_evidence_rule`, whether configured source/release switches remain operator intent rather than effective external calls, and whether those rows remain frontend-visible, non-editable, no-writeback, no-secret, and non-production evidence.
- Ordinary task-boundary visibility: when a round touches an ordinary entrance or its shared runtime/status source, state whether `任务边界` remains in the user summary before Settings / Developer / Audit details, whether `GET cache` / React render stayed read-only, and whether any `manual` or `live_light`补证 path still goes through `POST task` / worker / local fallback.
- Ordinary source-state chips: when a round touches an ordinary entrance or shared user-facing status wording, state whether `cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result` remain visible as read-only UI guidance, and confirm the chips did not create tasks, call provider/model, write cache/config, or promote production evidence.
- Ordinary next-click rule: when a round touches `Daily Command Center`, `Stock Quant Projection`, `Candidate Radar`, search submit, or shared user-facing status wording, state what the one primary safe next click is, whether disabled/degraded reasons are visible, and whether any work-creating click still goes through POST task / worker / local fallback with task status and no-trade/no-action boundaries.
- Engineering-audit demotion: when a round touches an ordinary page, state whether engineering contract tables, receipt rows, runbooks, and LTG audit surfaces remain behind Settings / Developer / Audit or are directly needed to explain the current user decision surface; they must not become the default ordinary-page body.
- Priority alignment: name which current migration priority was advanced (`push gate / CI`, `Legacy Bug / UX Audit`, `Candidate Radar`, searched-symbol -> `生成 3.0 量化推演`, provider/model/cache/pending state, or engineering-audit demotion) and say when a round deliberately advanced none.
- CI / release evidence boundary: when a round touches release, push-gate, production promotion, or P0 status, state whether the evidence is only local validation or a matching current remote CI review. Local tests, local push gate, static workflow files, checklist wording, receipts, and stage-scope rows are not remote CI evidence. Release or production-replacement claims remain blocked until there is a matching head SHA/commit with current GitHub Actions green status or reviewed failure logs, plus explicit user push confirmation before any push.
- Remote CI unknown rule: if the user did not explicitly request GitHub/Actions inspection in the round, report remote CI status as unknown and do not infer green, red, or release readiness from local validation, local push-gate output, workflow-file presence, old emails, or previous remote runs.
- Ordinary-entrance state: when a round touches `Daily Command Center`, `Stock Quant Projection`, or `Candidate Radar`, state how next click, Tushare/cache/DeepSeek/pending source, missing evidence, research-only not-buy/sell boundary, blocked/degraded state, and last successful cache/result are shown or intentionally unchanged.
- Current repository state.
- Push status.
- One recommended next small patch.

## Why This Protocol Exists

The project has several heavy and stateful chains: DeepSeek explanations, backtests, Tushare and AkShare data refreshes, next ticket radar scans, and ETF discovery. A fixed handoff protocol keeps each upgrade small, validated, committed or checkpointed, and safe for the next ChatGPT planning round.
