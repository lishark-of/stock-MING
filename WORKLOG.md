# WORKLOG

## 2026-05-14 Feed Metadata And Dedup Verification Rerun

- Goal: re-check the existing metadata/tags and duplicate document handling changes after the task was repeated in chat.
- Modified files:
  - `WORKLOG.md`
- Code status:
  - No additional app logic changes were made in this rerun.
  - Existing implementation remains in `app.py`.
- Test results:
  - `python3 -m py_compile app.py analysis_engine.py data_fetcher.py backtester.py money_flow_tracker.py visualizer.py config.py` passed.
  - `python3 -m unittest discover -s tests -v` passed, 7 tests run.
  - `bash run_local.sh` started Streamlit at `http://localhost:8502`.
  - `curl -I http://localhost:8502` returned HTTP 200 OK.
  - Existing duplicate hash verification returned `brain_memory_matches=1` and `stock_reports_matches=1`.
  - `.streamlit/secrets.toml` was not tracked by Git.
- Note:
  - Chrome had an old `localhost:8501` tab with a stale dependency error and the browser automation address input mangled `localhost:8502`; the app server itself was verified healthy on port 8502.
- Recommended next steps:
  - Commit `app.py` and `WORKLOG.md` if the current behavior is accepted.

## 2026-05-14 Feed Metadata And Dedup Update

- Goal: add stable metadata/tags and content_hash deduplication for manual feed/document extraction so later stock diagnosis can recall structured memories more reliably.
- Modified files:
  - `app.py`
  - `WORKLOG.md`
- Metadata/tags storage:
  - No Supabase table structure was changed.
  - `brain_memory.content` now stores extraction JSON with top-level `metadata`, `content_hash`, `document_type`, and `extraction_status`.
  - `stock_reports.report_content` receives the enriched extraction payload with the same `metadata` object.
  - `manager_rules.source` receives a short hash suffix when rules are written; rule text remains plain text to avoid changing downstream manager-rule semantics.
- Metadata fields:
  - `document_type`, `extraction_status`, `tickers`, `company_names`, `industries`, `themes`, `risk_tags`, `time_window`, `source_file`, `content_hash`, `extracted_at`, `evidence_summary`.
  - Missing explicit tags are stored as `[]`, `unknown`, `low_confidence`, or `原文未提供`; no labels are invented to fill blanks.
- Dedup logic:
  - `content_hash` is generated with SHA-256 over normalized raw input/file text, independent of filename.
  - Before writing `brain_memory` or `stock_reports`, the app searches existing JSON text with `.ilike("%content_hash%")`.
  - Duplicate content skips repeat `brain_memory`, `stock_reports`, and `manager_rules` writes and shows a duplicate-hit message in the UI.
- Test results:
  - `python3 -m py_compile app.py analysis_engine.py data_fetcher.py backtester.py money_flow_tracker.py visualizer.py config.py` passed.
  - `python3 -m unittest discover -s tests -v` passed, 7 tests run.
  - `bash run_local.sh` started Streamlit at `http://localhost:8502`.
  - Chrome opened `localhost:8502`; manual feed test showed metadata/tags and manager_rules=0 reason.
  - Repeating the same feed showed duplicate hit and skipped repeat writes.
  - Hash verification found `brain_memory_matches=1` and `stock_reports_matches=1` for the test content hash.
  - `.streamlit/secrets.toml` was not tracked by Git.
- App status: opens locally on `http://localhost:8502`; no real keys were printed during checks.
- Recommended next steps:
  - Commit `app.py` and `WORKLOG.md` if the current behavior is accepted.
  - Later consider adding real `metadata`/`content_hash` columns or indexes in Supabase for faster exact dedup queries; do this as a planned migration, not an app-side silent change.
  - Next functional step can be diagnosis recall by `ticker`, `industry`, and `theme`.

## 2026-05-13 Feed Extract Display Card Update

- Current branch: `work` tracking `origin/work`
- Current uncommitted changes before WORKLOG update: `app.py`
- Latest completed feature: optimized资料投喂/云端神经元记忆档案 display from raw `[STRATEGY]` JSON/text into structured cards
- Current unfinished tasks: none identified; no交易逻辑、回测逻辑、资金链路 or Supabase table structure changes were made
- Test results:
  - `python3 -m py_compile app.py analysis_engine.py data_fetcher.py backtester.py money_flow_tracker.py visualizer.py config.py` passed
  - `python3 -m unittest discover -s tests -v` passed, 7 tests run
  - Streamlit app started locally at `http://127.0.0.1:8505` and returned HTTP 200 OK
- Recommended next steps:
  - Manually review one real feed result in the UI to confirm field grouping matches expectations
  - Commit `app.py` and `WORKLOG.md` together if the display behavior is accepted

## 2026-05-13 Recovery Check

- Current branch: `work` tracking `origin/work`
- Current uncommitted changes before WORKLOG update: none
- Latest completed feature: `9121e2e Add state-aware trade logic and AI extraction workflow`
- Current unfinished tasks: none identified during recovery check; next work should be confirmed before adding functionality
- Test results:
  - `python3 -m py_compile app.py analysis_engine.py data_fetcher.py backtester.py money_flow_tracker.py visualizer.py config.py` passed
  - `python3 -m unittest discover -s tests -v` passed, 7 tests run
- Recommended next steps:
  - Review and commit `WORKLOG.md` if this recovery record should be preserved
  - Keep the next change small and run the same compile/test checks before any push
