#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "command_center_3_secret_keyword_review_contract.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = [
    "server",
    "worker",
    "storage",
    "desktop/src",
    "app.py",
    "command_center_factor_research.py",
    "tests",
    "docs",
    "scripts",
]
KEYWORD_PATTERN = (
    r"api_key|token|secret|password|Authorization|Bearer|DEEPSEEK|TUSHARE|"
    r"GITHUB_TOKEN|AKSHARE|apikey|access_key"
)
HIGH_RISK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"Bearer[ \t]+[A-Za-z0-9._-]{20,}|"
    r"(api_key|apikey|token|secret|password)[ \t]*=[ \t]*[\"'][^\"']{12,}[\"'])",
    re.IGNORECASE,
)


def _run_git_grep() -> list[tuple[str, int, str]]:
    cmd = ["git", "grep", "-nEI", KEYWORD_PATTERN, "--", *SCAN_PATHS]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    if proc.returncode == 1:
        return []
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "git grep failed").strip())
    rows: list[tuple[str, int, str]] = []
    for raw_line in proc.stdout.splitlines():
        parts = raw_line.split(":", 2)
        if len(parts) != 3:
            continue
        path, line_no, text = parts
        try:
            line_number = int(line_no)
        except ValueError:
            line_number = 0
        rows.append((path, line_number, text))
    return rows


def _high_risk_outside_allowed(path: str, text: str) -> bool:
    if path.startswith("tests/") or path.startswith("docs/") or path.endswith(".md"):
        return False
    if path == "desktop/src-tauri/Cargo.lock":
        return False
    return HIGH_RISK_PATTERN.search(text) is not None


def _classify(path: str, text: str) -> str:
    lower_path = path.lower()
    lower_text = text.lower()
    if lower_path.startswith("tests/"):
        return "tests_fixture_or_assertion"
    if lower_path.startswith("docs/"):
        return "docs_policy_or_plan"
    if lower_path.startswith("scripts/"):
        return "scripts_gate_or_scan"
    if lower_path.startswith("desktop/src/"):
        return "frontend_boundary_display"
    if path == "app.py":
        return "legacy_streamlit_guarded_code"
    if any(marker in lower_text for marker in ("sensitive_", "contains_secret", "redact", "safe_text", "secret_markers")):
        return "sanitizer_or_redaction_code"
    if any(marker in lower_text for marker in ("deepseek", "tushare", "github", "akshare")):
        return "provider_model_config_or_boundary"
    return "local_code_review_required"


def build_contract() -> dict[str, Any]:
    keyword_rows = _run_git_grep()
    category_counts: Counter[str] = Counter()
    file_counts: Counter[str] = Counter()
    high_risk_rows: list[dict[str, Any]] = []
    for path, line_no, text in keyword_rows:
        category_counts[_classify(path, text)] += 1
        file_counts[path] += 1
        if _high_risk_outside_allowed(path, text):
            high_risk_rows.append({"path": path, "line": line_no, "category": _classify(path, text)})

    category_rows = [
        {
            "category": category,
            "hit_count": count,
            "raw_keyword_lines_emitted": False,
            "review_policy": "structured_count_only_manual_review",
        }
        for category, count in sorted(category_counts.items())
    ]
    top_file_rows = [
        {"path": path, "hit_count": count, "raw_keyword_lines_emitted": False}
        for path, count in file_counts.most_common(20)
    ]
    high_risk_count = len(high_risk_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked_high_risk_keyword_value" if high_risk_count else "secret_keyword_review_contract_ready_manual_review_pending",
        "scope": "local_tracked_source_keyword_review_no_raw_line_output",
        "scan_paths": SCAN_PATHS,
        "keyword_pattern": KEYWORD_PATTERN,
        "keyword_hit_count": len(keyword_rows),
        "category_count": len(category_rows),
        "high_risk_tracked_value_count": high_risk_count,
        "manual_review_required": bool(keyword_rows),
        "periodic_allowlist_review_pending": bool(keyword_rows),
        "raw_keyword_lines_emitted": False,
        "outputs_source_line_text": False,
        "category_rows": category_rows,
        "top_file_rows": top_file_rows,
        "high_risk_rows": high_risk_rows,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "note": "This script classifies tracked keyword hits by path/category and intentionally does not print raw matched source lines.",
    }


def main() -> int:
    contract = build_contract()
    print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if contract["high_risk_tracked_value_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
