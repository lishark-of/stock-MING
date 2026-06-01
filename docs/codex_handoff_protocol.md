# Codex Handoff Protocol

This project uses a fixed handoff loop for ChatGPT-guided development:

ChatGPT designs task
-> User pastes task to Codex
-> Codex executes, validates, commits
-> Codex returns CHATGPT_HANDOFF
-> User pastes CHATGPT_HANDOFF to ChatGPT
-> ChatGPT designs next task

## Operating Rules

- The user should not manually run git, tests, py_compile, or smoke checks.
- Codex owns the local execution loop: inspect, edit, validate, and commit.
- Codex commits by default after successful validation.
- Codex does not push by default.
- Each round should be a small, reversible patch.
- One task should usually become one coherent commit.
- If a task spans unrelated concerns, split it into separate commits.

## stock-MING Safety Boundary

- Heavy trading and data operations must remain button gated.
- DeepSeek must not run automatically when a page opens.
- Backtests must not run automatically when a page opens.
- Full market scans must not run automatically when a page opens.
- Tushare cross-sectional scans must not run automatically when a page opens.
- AkShare heavy refreshes must not run automatically when a page opens.
- The legacy workspace must remain reachable unless a task explicitly changes that.
- Service layers should remain UI-free.
- UI layers should consume packet-like data from services.
- Packets should stay JSON-friendly where possible.

## End-of-Round Report

Every Codex round should end with a `CHATGPT_HANDOFF` report that includes:

- Summary of what changed.
- Commit hash and message.
- Changed file list.
- Validation results.
- Diff stat or commit summary.
- Risk notes.
- Current repository state.
- Push status.
- One recommended next small patch.

## Why This Protocol Exists

The project has several heavy and stateful chains: DeepSeek explanations, backtests, Tushare and AkShare data refreshes, next ticket radar scans, and ETF discovery. A fixed handoff protocol keeps each upgrade small, validated, committed, and safe for the next ChatGPT planning round.
