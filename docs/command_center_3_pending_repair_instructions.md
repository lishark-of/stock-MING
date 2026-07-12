# Command Center 3.0 Pending Repair Instructions

Updated: 2026-07-05

This file is the short handoff list after the user-usable vertical slice. Do not treat these items as 14 LTG closeout. Each item should be run as one small Codex goal, with at most one main target and one support target.

## Current Operating Goal

Command Center 3.0 is currently in user-usable vertical-slice mode, not 14 LTG strict-closeout mode.

Default work should improve the ordinary local research client first: home, Candidate Radar, ETF / Margin, Stock Quant Projection, and Next Session should show whether the app is usable, what the current symbol/result is, what to click next, what source is being read, and what remains missing. Engineering audit material stays available, but it should be collapsed under Research Assist / Audit Details or moved to developer routes.

Blocked should not be used merely because all 14 LTG are not closed. Use blocked only when the current vertical slice has no local, read-only, or button-gated work left and the next step needs explicit authorization for Tushare, worker/provider execution, GitHub, push, remote CI, DeepSeek, or trading-adjacent paths.

## Long-Term LTG Lookup Protocol

When the user mentions "长期目标", "14 LTG", "strict closeout", "大目标", or asks what remains unfinished, do this before answering:

1. Read `docs/command_center_3_long_term_goals.md` for the canonical 14 LTG list and acceptance language.
2. Read `docs/migration_map.md` for route ownership and migration state.
3. Run or inspect `scripts/ltg_progress_snapshot.py` when a current machine-readable snapshot is needed.
4. Check `/api/migration/status` when the local FastAPI is running, because strict closeout must not be inferred from UI slices.
5. Compare those sources with this file's `Next Repair Goals` before proposing the next goal.

Current interpretation:

- User-usable vertical slices can move ordinary usability forward without closing an LTG.
- Candidate Radar ordinary usability mainly belongs to LTG-13, with LTG-05, LTG-10, and LTG-12 as support boundaries.
- ETF / Margin ordinary usability is a legacy workflow extraction, supported by LTG-05, LTG-10, and LTG-12; it is not a standalone 14 LTG closeout.
- DeepSeek governed executor remains separate and should not block Tushare-first, local graph, Candidate Radar, or ETF / Margin usability.
- Remote CI / release review remains a release blocker, not a daily usability blocker.

## Current Done Slice

1. Candidate Radar now has a compact operator panel before the long research detail surface.
2. ETF / Margin has a React route that reads local `command_center_etf_packet` and `command_center_margin_packet`.
3. ETF / Margin is visible from the ordinary sidebar entrance.
4. Both surfaces keep page-open, render, input, and GET cache read-only. Refresh buttons only re-read local packets.
5. Home ordinary surface is verified as a first-card workflow: local connected, current symbol, recent result, next action, and status note stay above the collapsed Research Assist / Audit Details area.
6. ETF / Margin candidate rows now surface source, row status, reason, liquidity, overlap, cash/leverage guardrail, and no-buy/no-margin boundary before audit details.
7. User Route QA now has an explicit local runner/runbook for `#home`, `#candidates`, `#marginEtf`, `#factor`, and `#next`; reports and screenshots stay under ignored `.stock_ming_3/user_route_qa`.
8. Call Ledger Audit now reads ignored User Route QA reports through `user_route_qa_evidence_contract`, showing ordinary route visual QA, typing/task silence, Candidate Radar route pass state, local report counts, and no-provider/no-trade boundaries without opening a browser or committing screenshots.
9. Candidate Radar ordinary first screen now explains retirement-readiness as "退旧雷达前还缺什么" instead of leading with production/stage blocker wording; detailed gap rows stay collapsed and the slice remains local read-only evidence, not LTG-13 strict closeout.
10. Stock Quant Projection / Factor Quant Hub now shows LTG-03 true small-pool validation as an authorization-waiting state on the ordinary first screen: local scope and execution-request tickets are historical/read-only, and real provider task/sample/rolling/cost/neutralization evidence still requires explicit user authorization.
11. ETF / Margin now has a button-gated local task contract: `POST /api/market/margin-etf-local-refresh` writes a safe `command_center_margin_etf_refresh_receipt`, the page shows disabled/degraded reasons before the click, and `TaskStatusPanel` shows the local task status after the click. This remains a local packet replay, not provider refresh, Streamlit retirement, or LTG strict closeout.
12. User Route QA now requires actual typing coverage before accepting typing silence: if a route has visible editable inputs, the runner fills one with a test symbol and only passes when `/api/tasks` stays unchanged.
13. Candidate Radar ordinary summary now shows a local page-QA quick read from `candidate_browser_qa_evidence_summary` / review status before developer audit details, while keeping the review POST button in the collapsed audit section and preserving the no-CI/no-provider/no-worker boundary.
14. Storage now exposes the LTG-05 physical evidence local task chain on the ordinary first screen: `physical execution request` and `Phase A local evidence` buttons show receipt/status via `TaskLaunchReceipt` and `TaskStatusPanel`; the same ordinary screen also shows current-result atomic promotion/readback state, expected symbol/result version, current/last-good, and retention guardrails. These remain local storage evidence/readback only: GET/render creates no task, physical evidence buttons do not call providers/models/GitHub, current-result reads do not refresh provider/model data, no trading action is created, and `production_storage_complete=false`.
15. Worker now exposes the LTG-06 runtime QA local task chain on the ordinary first screen: `runtime QA request`, `runtime QA dry-run`, and `local QA execution` buttons show receipt/status via `TaskLaunchReceipt` and `TaskStatusPanel`, while still starting no Celery/Redis/APScheduler process, pinging no Redis, dispatching no provider/model task, calling no providers/models/GitHub, and keeping `production_worker_complete=false`.
16. Next Session now exposes the LTG-08 local evidence review chain on the ordinary first screen: browser QA artifact review, same-packet retained coverage review, and promotion blocker review buttons show receipt/status via `TaskLaunchReceipt` and `TaskStatusPanel`, while still opening no browser, writing no screenshots/report artifact, calling no providers/models/GitHub, executing no trades, and keeping `production_replacement_complete=false`.
17. Desktop / Tauri now exposes the LTG-09 local package evidence review chain on the ordinary first screen: release artifact, packaged launch, offline UX, backend runtime, config/log, signing/notarization, and promotion blocker buttons show receipt/status via `TaskLaunchReceipt` and `TaskStatusPanel`, while still running no npm/cargo/Tauri build, opening no packaged app, starting no FastAPI, reading no config values, writing no logs, calling no providers/models/GitHub, executing no trades, and keeping `production_package_complete=false`.
18. Legacy / Streamlit now exposes the LTG-10 local retirement evidence review chain on the ordinary first screen: ordinary workflow parity review and fallback retirement blocker review buttons show receipt/status via `TaskLaunchReceipt` and `TaskStatusPanel`, while still opening no Streamlit, running no legacy tools, removing no fallback, deleting no `app.py`, calling no providers/models/GitHub, executing no trades, and keeping `streamlit_retirement_complete=false`.
19. Candidate Radar ordinary first screen now exposes the LTG-13 next direct-evidence quick read: searched-symbol real-data ledger and final promotion review are shown as the two remaining gaps, with an explicit authorization-required disabled state and a jump to the folded audit area, while still not running Tushare, DeepSeek, GitHub, worker, browser, or trading work from render.

## Next Repair Goals

1. Candidate Radar De-noise
   - Goal: keep the new operator panel as the first ordinary surface and move repeated P1/P2/P3 tables under collapsed research details.
   - Preserve confirm button, TaskStatusPanel, local replay refresh, and candidate pool visibility.
   - Current local slice: production/stage blocker language has been translated into ordinary retirement-readiness wording; opening `#candidates` should show what the user can do, what remains before old-radar retirement, local page-QA artifact/review state, the LTG-13 next direct-evidence pair, and the no-trade boundary before any audit row tables.
   - Exit check: opening `#candidates` does not look like an acceptance report, and any worker/provider/browser/legacy gap rows remain collapsed by default.

2. ETF / Margin Task Contract
   - Goal: add a manual POST task for refreshing or rebuilding the ETF / Margin local packet.
   - Boundary: no automatic page-open refresh; no model call; no trade; no token/key in payload, log, packet, or frontend.
   - Current local slice: `#marginEtf` already exposes the button, disabled/degraded reason, safe receipt, and `TaskStatusPanel` for `/api/market/margin-etf-local-refresh`. Do not repeat this as the next target unless QA finds a regression.
   - Exit check: the page shows disabled/degraded reason when the task is unavailable and shows task status when clicked.

3. ETF / Margin Evidence Quality
   - Goal: improve ETF candidate rows with source, liquidity, overlap, cash buffer, and leverage guardrail.
   - Current local slice: visible rows now expose those fields before audit details; this is still an ordinary usability slice, not Streamlit fallback retirement or LTG strict closeout.
   - Boundary: ETF candidate is not a buy instruction; margin ratio is not permission to add leverage.
   - Exit check: each visible ETF row explains why it is recommended, watched, avoided, or excluded.

4. User Route QA
   - Goal: browser-check `#home`, `#candidates`, `#marginEtf`, `#factor`, and `#next` on desktop and mobile widths.
   - Current local slice: `scripts/user_route_qa_runner.mjs` can run the ordinary route matrix against already-running local FastAPI/Vite, type into visible editable inputs without submit, require typing coverage when inputs are present, and compare `/api/tasks` counts before/after render/typing.
   - Current readback: `GET /api/audit/cache` surfaces `user_route_qa_evidence_contract` and rows from ignored local reports, including the `#candidates` pass state and task-silence count.
   - Check text overflow, repeated audit noise, disabled button reasons, and local-only refresh behavior.
   - Exit check: screenshots or notes prove first viewport clarity and no task is created by render or typing.

5. Factor Test Lab Small-Pool Authorization Clarity
   - Goal: keep the ordinary Factor Quant Hub page clear that LTG-03 true small-pool validation has not run unless provider task/sample evidence exists.
   - Current local slice: ordinary first screen now shows whether true small-pool validation has run, whether authorization is still needed, and which provider task/sample/rolling/cost/neutralization evidence remains missing.
   - Boundary: do not rerun local dry-run or execution-request as the next LTG-03 action; real provider validation requires explicit user authorization and call-ledger/sample evidence.
   - Exit check: opening `#factor` makes the next authorized provider task obvious without making local tickets look like production validation.

6. DeepSeek Governed Executor
   - Goal: implement separately after Tushare-first and local graph views are usable.
   - Boundary: DeepSeek may explain only allowed fields; it must not overwrite price, holdings, factors, operation zones, strategy action, or radar candidates.
   - Exit check: model ledger, sanitizer, output acceptance, field whitelist, and no-secret evidence are visible before any real call.

7. Remote CI / Release Review
   - Goal: inspect matching GitHub Actions for the current pushed commit only after explicit user authorization.
   - Boundary: no push or GitHub API without explicit authorization.
   - Exit check: CI failure emails are mapped to exact failing jobs and fixed in the smallest possible patch.

## Suggested Goal Template

```text
/goal
Command Center 3.0 使用者可用化纵切 + 长期 LTG 未完成项可追踪。

本轮只做 1 个主目标 + 1 个支撑目标，最多改 5 个文件。
主目标：从 docs/command_center_3_pending_repair_instructions.md 选择一个未完成项。
支撑目标：只补必要测试、文案下沉或本地只读验证。

长期目标规则：
如果我提到长期目标、14 LTG、strict closeout 或大目标，先查 docs/command_center_3_long_term_goals.md、docs/migration_map.md、scripts/ltg_progress_snapshot.py 和 /api/migration/status，再告诉我未完成部分、缺口证据和下一条最短 direct evidence chain。

边界：
页面打开、输入、React render、GET cache 不自动外联。
工作创建只允许按钮触发 POST task / worker / local fallback。
不调用 DeepSeek、GitHub、真实交易；Tushare 只有我明确授权才调用。
token/key 不进前端、日志、packet、cache。
不把本阶段称为 14 LTG 完成。
不因 14 LTG strict_closeout 未完成而反复 blocked；blocked 只用于当前纵切无本地可推进事项且缺少必要授权。

结束输出 checkpoint：
目标、对应 LTG 或 legacy 来源、修改文件、验证命令、是否外联、是否交易、用户现在能看到什么、长期 LTG 是否前进、下一步最短动作。
```
