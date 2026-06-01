# stock-MING App Migration Plan

## 1. Current State

stock-MING is currently a local trading decision app with a Streamlit main application and a pywebview desktop shell. The Streamlit app remains the primary runtime surface, while `desktop_app.py` wraps the local Streamlit server into a desktop-like window.

The product center of gravity has moved to 综合推演中心 2.0. It is now the default core workspace and presents the main trading workflow through packetized service outputs, including the command center live packet, strategy execution packet, and command center decision packet.

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

Heavy tasks must remain button gated. Opening the app must not automatically call DeepSeek, run full backtests, trigger full-market scans, or execute slow Tushare/AkShare/yfinance/Supabase paths.

## 2. Migration Goals

The migration should make stock-MING feel more like a stable local product and less like a web page embedded in a shell. The goals are:

- Build a more native App experience.
- Reduce visible Streamlit web-app feel.
- Make startup more stable and diagnosable.
- Improve the left navigation and first-screen decision experience.
- Keep the trading decision loop clear: refresh data, generate strategy execution advice, generate daily decision, optionally ask DeepSeek to explain.
- Preserve the current business chain and existing legacy workbench while new surfaces mature.
- Avoid a full rewrite that creates white screens, performance regressions, data refresh regressions, or feature loss.

## 3. Options Compared

### Option A: Continue pywebview + Streamlit polish

This option keeps the current architecture and improves the desktop shell, Streamlit defaults, startup diagnostics, navigation, and first-screen command center experience.

- Development cost: low to medium. Most work is incremental.
- Code reuse rate: very high. Existing Streamlit pages, service packets, DeepSeek paths, data adapters, backtests, radar, and ETF modules remain usable.
- Current feature stability: highest. This option changes the least about the execution model.
- App native feel: limited but improvable. pywebview can hide some browser feel, improve window title, menu/Dock naming, and provide a more focused shell, but Streamlit still leaks through in layout and runtime behavior.
- Packaging complexity: medium. It still depends on local Python, `.venv`, Streamlit subprocess management, and macOS wrapper details.
- White screen risk: lower than a rewrite, but still present if Streamlit subprocess startup fails or pywebview cannot reach the local port.
- Impact on DeepSeek / Tushare / AkShare / Supabase: minimal. Existing gated flows stay intact.
- Fit: best short-term path. It is the safest way to keep shipping while reducing product friction.

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

Short term: continue with pywebview + Streamlit polish. Harden the desktop shell, improve startup diagnostics, make the command center feel more product-like, and preserve all current business flows.

Medium term: gradually extract command center adapters from `app.py` so the UI consumes packets instead of owning orchestration. Keep service modules UI-free and keep packet outputs JSON-friendly.

Long term: prioritize a Tauri + React + Python local API pilot, starting only with 综合推演中心 2.0. Do not migrate the entire legacy workbench at once.

不建议现在直接全量迁移到 React/Tauri。

The reasons are:

- `app.py` still owns a large amount of legacy page logic.
- DeepSeek, backtesting, Tushare full scans, next ticket full scans, ETF discovery, and data refresh chains are complex.
- Service-layer packetization does not yet cover every module and every old workbench path.
- A full migration can easily introduce white screens, performance regressions, data refresh bugs, packaging failures, and feature regressions.

The safer path is to keep Streamlit as the reliable fallback while progressively making the command center API-like, then use that stable packet surface for a native pilot.

## 5. Phased Roadmap

### Phase 1: Desktop shell hardening

- Add startup self-checks.
- Show a clear message when `.venv` is missing.
- Show a clear message when ports are occupied.
- Add a Streamlit subprocess error page instead of a blank desktop window.
- Add App icon support.
- Make macOS menu and Dock names consistently show stock-MING.
- Default directly into 综合推演中心 2.0.
- Continue to prevent automatic heavy task execution.

### Phase 2: Command center adapter extraction

- Extract command center adapter logic from `app.py`.
- Keep the Streamlit UI for now.
- Keep service modules free of UI imports.
- Keep packets JSON-friendly.
- Do not change DeepSeek, Tushare, AkShare, Supabase, or backtest business logic.

### Phase 3: Local API layer

- Establish a local API layer for packet consumption.
- Expose only lightweight packet endpoints by default.
- Keep all heavy tasks button gated.
- Require explicit user action for DeepSeek calls.
- Require explicit user action for backtests.
- Require explicit user action for Tushare full scans and other heavy market scans.

### Phase 4: Tauri / React pilot

- Rebuild only the command center home screen in Tauri + React.
- Consume `command_center_live_packet`, `strategy_execution_packet`, and `command_center_decision_packet`.
- Do not migrate the old workbench in this phase.
- Keep the old Streamlit app available as an advanced legacy mode.

### Phase 5: Gradual module migration

- Migrate strategy execution first.
- Migrate daily command center decision next.
- Migrate margin ETF.
- Migrate next ticket radar.
- Migrate trading discipline.
- Migrate quant inference.

### Phase 6: Legacy Streamlit retirement decision

- Decide whether to hide or retire the old Streamlit workbench only after the core command center chain is stable in the native surface.
- Keep a rollback path until the native path has covered the real daily workflow.

## 6. Architecture Principles

- Service modules must not contain UI rendering.
- Frontends should consume packets, not reach into Streamlit page state.
- Packets must be JSON-friendly.
- All heavy tasks must remain button gated.
- DeepSeek must never run automatically.
- Backtests must never run automatically.
- Full-market scans must never run automatically.
- Tushare cross-section scans must never run automatically.
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

1. Commit the current strategy execution card patch as the current productization checkpoint.
2. Add `docs/app_migration_plan.md`.
3. Next round: harden `desktop_app.py` startup self-checks and error page.
4. Following round: extract the command center adapter from `app.py`.
5. Start a Tauri / React pilot only after the packet and local API boundary is stable.

## 9. Non-goals

- Do not fully rewrite the frontend in this stage.
- Do not remove Streamlit.
- Do not remove the legacy workbench.
- Do not change service contracts.
- Do not change DeepSeek call logic.
- Do not change Tushare, AkShare, or Supabase data chains.
- Do not change the backtest engine.
- Do not add automated trading.
- Do not add automatic heavy-position recommendations.
