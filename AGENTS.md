# AGENTS.md

## Working agreements

- Codex should own execution: inspect, edit, validate, and commit.
- The user should not be asked to run git, tests, py_compile, or smoke checks manually.
- Do not push unless the user explicitly says to push.
- Keep patches small and reversible.
- Prefer one coherent commit per task.
- Before editing, inspect git status and diff.
- After editing, run the relevant validation commands.
- If validation fails, fix the issue or clearly report why it is unrelated.
- Always finish with a CHATGPT_HANDOFF report.

## stock-MING safety rules

- Do not auto-run DeepSeek.
- Do not auto-run backtests.
- Do not auto-run full market scans.
- Do not auto-run Tushare cross-sectional scans.
- Do not auto-run AkShare heavy refreshes.
- All heavy operations must remain button gated.
- Preserve legacy workspace entry points.
- Do not rewrite service contracts unless explicitly requested.
- Service layers must remain UI-free.
- Frontend/render layers should consume packet-like data.
- Packets should stay JSON-friendly when possible.

## Commit rules

- Commit after successful validation.
- Do not push by default.
- Use clear commit messages.
- Include git status and latest commit hash in the final report.

## CHATGPT_HANDOFF format

Every final response must include:

CHATGPT_HANDOFF

1. Summary
- What was changed:

2. Commit
- Hash:
- Message:

3. Changed files
- File list:

4. Validation
- py_compile:
- unittest:
- smoke test:
- other checks:

5. Diff stat
- Output of git diff --stat before commit, or commit diff summary:

6. Risk notes
- Known risks:
- What was intentionally not changed:

7. Current repository state
- git status:
- push status: No, unless explicitly requested

8. Suggested next task
- One recommended next small patch:
