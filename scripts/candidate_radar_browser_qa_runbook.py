#!/usr/bin/env python3
"""Local LTG-13 Candidate Radar browser QA runbook.

This script does not open a browser, start servers, call providers, call models,
or execute trades. It pins the Candidate Radar route, viewport matrix, visual
checks, performance budgets, and shared local runner boundaries for the later
explicit browser pass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = ROOT / "scripts" / "motion_browser_qa_runner.mjs"
CANDIDATE_ROUTE = ROOT / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
ARTIFACT_ROOT = ".stock_ming_3/motion_qa"
LOCAL_VITE_BASE = "http://127.0.0.1:4173"
LOCAL_API_BASE = "http://127.0.0.1:8710"

QA_ROUTE = {
    "route": "#candidates",
    "label": "Candidate Radar",
    "risk_focus": "radar result cluster, local scan controls, result-delta visibility, and no-trade boundaries",
}
QA_VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "laptop", "width": 1280, "height": 800},
    {"name": "tablet", "width": 834, "height": 1112},
    {"name": "mobile", "width": 390, "height": 844},
]
PERFORMANCE_BUDGETS = {
    "candidate_radar_first_stable_us": 1_200_000,
    "route_transition_observed_us": 500_000,
    "largest_motion_layout_shift_ppm": 100_000,
    "long_task_over_50ms_count": 0,
}
VISUAL_ACCEPTANCE_CRITERIA = [
    "candidate result cluster remains readable without opening raw JSON",
    "quick/watchlist/custom/full-pool/deep-scan controls remain visibly button-gated",
    "result-delta and previous-cache rows do not imply a trade recommendation",
    "provider/freshness/degraded gaps remain visible and are not hidden by motion",
    "mobile layout does not clip primary labels, state clarity rails, or action buttons",
    "reduced-motion mode preserves readable state boundaries",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _row(phase: str, status: str, evidence: str, *, required_before_completion: bool = True) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "evidence": evidence,
        "required_before_completion": required_before_completion,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def build_runbook() -> dict[str, Any]:
    runner = _read(RUNNER_SCRIPT)
    candidate_source = _read(CANDIDATE_ROUTE)
    runner_available = (
        RUNNER_SCRIPT.exists()
        and "command_center_3_motion_browser_qa_result.v7" in runner
        and "explicit_local_browser_visual_performance_run" in runner
        and "chromium.launch" in runner
        and "page.goto" in runner
        and "#candidates" in runner
        and "Candidate Radar" in runner
        and ARTIFACT_ROOT in runner
        and "starts_no_servers" in runner
        and "local_urls_only" in runner
        and "external_calls_triggered: false" in runner
        and "does_not_execute_trades: true" in runner
        and "execFileSync(\"git\"" in runner
        and "--expected-head-full" in runner
        and ("tushare" + "_adapter") not in runner
        and ("deepseek" + "_adapter") not in runner
        and ("api.github" + ".com") not in runner
        and "place_order" not in runner
    )
    source_ready = (
        CANDIDATE_ROUTE.exists()
        and "radar-result-cluster" in candidate_source
        and "StateClarityRail" in candidate_source
        and "resultDeltaClarity" in candidate_source
        and "previousCacheDiffRows" in candidate_source
        and "postCandidateRadarQuickScan" in candidate_source
        and "postCandidateRadarFullPoolPlan" in candidate_source
        and "postCandidateRadarDeepScanPlan" in candidate_source
        and "refreshCache();" in candidate_source
        and "候选不是买入指令" in candidate_source
        and "不调用 Tushare、DeepSeek 或 GitHub" in candidate_source
    )
    matrix_rows = [
        {
            "route": QA_ROUTE["route"],
            "label": QA_ROUTE["label"],
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": QA_ROUTE["risk_focus"],
            "required_checks": [
                "candidate result cluster is visible and readable",
                "local scan buttons are visible and do not auto-run",
                "delta/freshness/provider/degraded gaps remain visible",
                "no clipped primary labels or state clarity rail text",
                "no long task above the local budget",
            ],
            "visual_qa_complete": False,
            "browser_performance_trace_done": False,
        }
        for viewport in QA_VIEWPORTS
    ]
    rows = [
        _row(
            "shared_local_runner_available",
            "passed_static_policy" if runner_available else "blocked",
            "scripts/motion_browser_qa_runner.mjs covers #candidates and writes ignored local artifacts only",
        ),
        _row(
            "candidate_route_source_ready",
            "passed_static_policy" if source_ready else "blocked",
            "CandidateRadar.tsx exposes result cluster, clarity rail, delta rows, and button-gated scan controls",
        ),
        _row(
            "local_url_boundary",
            "passed_static_policy",
            "Browser QA must visit only 127.0.0.1 Vite/FastAPI URLs and must not click provider/model/trading paths",
        ),
        _row(
            "visual_artifact_policy",
            "execution_pending",
            "Screenshots/reports belong under ignored .stock_ming_3/motion_qa and are not committed as durable production proof",
        ),
        _row(
            "default_motion_pass_pending",
            "execution_pending",
            "Run shared runner against the Candidate Radar route with default motion before claiming browser visual QA.",
        ),
        _row(
            "reduced_motion_pass_pending",
            "execution_pending",
            "Run shared runner with --reduced-motion before claiming accessibility coverage.",
        ),
        _row(
            "performance_trace_pending",
            "execution_pending",
            "Candidate Radar must meet first-stable, route-transition, long-task, and layout-shift budgets in browser.",
        ),
    ]
    blockers = [row["phase"] for row in rows if row["status"] == "blocked"]
    return {
        "schema_version": "candidate_radar_browser_qa_runbook.v1",
        "status": "candidate_radar_browser_qa_runbook_ready_execution_pending" if not blockers else "candidate_radar_browser_qa_runbook_blocked",
        "scope": "local_candidate_radar_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "local_runbook_ready": not blockers,
        "runner_available": runner_available,
        "candidate_route_source_ready": source_ready,
        "shared_runner_script": "scripts/motion_browser_qa_runner.mjs",
        "candidate_route": "#candidates",
        "local_vite_base": LOCAL_VITE_BASE,
        "local_api_base": LOCAL_API_BASE,
        "artifact_root": ARTIFACT_ROOT,
        "route_count": 1,
        "viewport_count": len(QA_VIEWPORTS),
        "qa_matrix_count": len(matrix_rows),
        "performance_budgets": PERFORMANCE_BUDGETS,
        "visual_acceptance_criteria": VISUAL_ACCEPTANCE_CRITERIA,
        "rows": rows,
        "qa_matrix": matrix_rows,
        "blocking_phase_count": len(blockers),
        "blockers": blockers,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "visual_qa_complete": False,
        "browser_performance_trace_done": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This runbook prepares a targeted Candidate Radar browser QA pass. It is not browser evidence, not provider-backed acceptance, and not production radar replacement.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the local LTG-13 Candidate Radar browser QA runbook.")
    parser.add_argument("--json", action="store_true", help="Print the runbook as JSON.")
    args = parser.parse_args()

    runbook = build_runbook()
    if args.json:
        print(json.dumps(runbook, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"candidate_radar_browser_qa_runbook: {runbook['status']}")
        print(
            "route: #candidates; viewports: {viewport_count}; qa_matrix: {qa_matrix_count}; "
            "visual_qa_complete: false; browser_performance_trace_done: false".format(**runbook)
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if runbook["blockers"]:
            print("blockers: " + ", ".join(runbook["blockers"]))
    return 0 if runbook["local_runbook_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
