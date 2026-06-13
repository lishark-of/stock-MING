#!/usr/bin/env python3
"""Local Command Center 3 motion browser QA runbook contract.

This script does not start FastAPI, Vite, Tauri, or a browser. It makes the
future LTG-14 browser visual/performance pass reproducible by pinning the local
startup sequence, viewport matrix, visual criteria, performance budgets, and
artifact policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ".stock_ming_3/motion_qa"
LOCAL_API_BASE = "http://127.0.0.1:8710"
LOCAL_VITE_BASE = "http://127.0.0.1:5173"
RUNNER_SCRIPT = ROOT / "scripts" / "motion_browser_qa_runner.mjs"

QA_ROUTES = [
    {"route": "#home", "label": "Command Center", "risk_focus": "page staging and status summary clarity"},
    {"route": "#next", "label": "Next Session Map", "risk_focus": "chart update clarity and reduced-motion chart updates"},
    {"route": "#candidates", "label": "Candidate Radar", "risk_focus": "radar result cluster and runtime-budget visibility"},
    {"route": "#tasks", "label": "Task Monitor", "risk_focus": "task phase confirmation and progress readability"},
    {"route": "#audit", "label": "Call Ledger Audit", "risk_focus": "motion audit rows and warning density"},
]

QA_VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "laptop", "width": 1280, "height": 800},
    {"name": "tablet", "width": 834, "height": 1112},
    {"name": "mobile", "width": 390, "height": 844},
]

VISUAL_ACCEPTANCE_CRITERIA = [
    "route context remains obvious without reading raw JSON",
    "state-change cues do not cover freshness, risk, blocker, or warning text",
    "candidate delta and chart update cues do not imply a trading recommendation",
    "buttons, tables, metric labels, and status badges do not overlap or clip",
    "reduced-motion mode preserves readable state boundaries with animation disabled",
]

PERFORMANCE_BUDGETS = [
    {"metric": "route_transition_observed_ms", "budget": 500, "scope": "hash route change after cache is loaded"},
    {"metric": "largest_motion_layout_shift", "budget": 0.1, "scope": "state confirmation cue and card staging"},
    {"metric": "long_task_over_50ms_count", "budget": 0, "scope": "route change, chart update, candidate radar render"},
    {"metric": "candidate_radar_first_stable_ms", "budget": 1200, "scope": "cache already local; no provider refresh"},
]


def _row(phase: str, status: str, evidence: str, *, required_before_completion: bool = True) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "required_before_completion": bool(required_before_completion),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_runbook() -> dict[str, Any]:
    runner_source = _read_text(RUNNER_SCRIPT)
    runner_available = (
        RUNNER_SCRIPT.exists()
        and "command_center_3_motion_browser_qa_result.v1" in runner_source
        and "explicit_local_browser_visual_performance_run" in runner_source
        and "chromium.launch" in runner_source
        and "page.goto" in runner_source
        and ".stock_ming_3/motion_qa" in runner_source
        and "starts_no_servers" in runner_source
        and "local_urls_only" in runner_source
        and "external_calls_triggered: false" in runner_source
        and "does_not_execute_trades: true" in runner_source
        and "child_process" not in runner_source
        and "uvicorn" not in runner_source
        and "npm run dev" not in runner_source
        and "tushare_adapter" not in runner_source
        and "deepseek_adapter" not in runner_source
        and "api.github.com" not in runner_source
        and "place_order" not in runner_source
    )
    route_rows = [
        {
            "route": route["route"],
            "url": f"{LOCAL_VITE_BASE}/{route['route']}",
            "label": route["label"],
            "risk_focus": route["risk_focus"],
            "visual_qa_complete": False,
            "performance_trace_complete": False,
        }
        for route in QA_ROUTES
    ]
    viewport_rows = [
        {
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "artifact_pattern": f"{ARTIFACT_ROOT}/<timestamp>/{viewport['name']}/<route>.png",
            "visual_qa_complete": False,
        }
        for viewport in QA_VIEWPORTS
    ]
    qa_matrix = [
        {
            "route": route["route"],
            "viewport": viewport["name"],
            "url": f"{LOCAL_VITE_BASE}/{route['route']}",
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": route["risk_focus"],
            "required_visual_checks": VISUAL_ACCEPTANCE_CRITERIA,
            "visual_qa_complete": False,
            "performance_trace_complete": False,
        }
        for route in QA_ROUTES
        for viewport in QA_VIEWPORTS
    ]
    runbook_rows = [
        _row(
            "start_fastapi_backend",
            "manual_required",
            "scripts/dev_server.sh uses project .venv and serves FastAPI on 127.0.0.1:8710",
        ),
        _row(
            "start_vite_frontend",
            "manual_required",
            "cd desktop && npm run dev serves local Vite on 127.0.0.1:5173",
        ),
        _row(
            "load_pinned_routes",
            "execution_pending",
            f"{len(QA_ROUTES)} local hash routes are pinned for visual QA",
        ),
        _row(
            "apply_viewports",
            "execution_pending",
            f"{len(QA_VIEWPORTS)} desktop/tablet/mobile viewports are pinned",
        ),
        _row(
            "capture_visual_artifacts",
            "execution_pending",
            f"screenshots or recordings should be stored under ignored local path {ARTIFACT_ROOT}",
        ),
        _row(
            "capture_performance_trace",
            "execution_pending",
            "record route transition, chart update, task panel, and candidate radar render budgets",
        ),
        _row(
            "verify_reduced_motion",
            "execution_pending",
            "run at least one desktop and one mobile pass with prefers-reduced-motion enabled",
        ),
        _row(
            "keep_artifacts_out_of_git",
            "passed_static_policy",
            "motion QA artifacts belong under .stock_ming_3 or another ignored local path",
        ),
        _row(
            "provider_trade_isolation",
            "passed_static_policy",
            "browser QA must only visit local FastAPI/Vite URLs and must not click provider/model/trading task buttons",
        ),
        _row(
            "explicit_runner_available",
            "passed_static_policy" if runner_available else "blocked",
            "scripts/motion_browser_qa_runner.mjs can execute the pinned local route/viewport matrix and write ignored local artifacts without starting services",
        ),
    ]
    local_runbook_ready = runner_available
    return {
        "schema_version": "command_center_3_motion_browser_qa_runbook.v1",
        "status": "motion_browser_qa_runbook_ready_execution_pending" if local_runbook_ready else "motion_browser_qa_runbook_blocked",
        "scope": "local_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-14",
        "local_runbook_ready": local_runbook_ready,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "production_motion_complete": False,
        "local_api_base": LOCAL_API_BASE,
        "local_vite_base": LOCAL_VITE_BASE,
        "runner_script": "scripts/motion_browser_qa_runner.mjs",
        "browser_runner_available": runner_available,
        "runner_executes_only_when_called": True,
        "runner_starts_no_servers": True,
        "runner_writes_ignored_local_artifacts": True,
        "artifact_root": ARTIFACT_ROOT,
        "route_count": len(QA_ROUTES),
        "viewport_count": len(QA_VIEWPORTS),
        "qa_matrix_count": len(qa_matrix),
        "visual_acceptance_criteria": VISUAL_ACCEPTANCE_CRITERIA,
        "performance_budgets": PERFORMANCE_BUDGETS,
        "runbook_rows": runbook_rows,
        "route_rows": route_rows,
        "viewport_rows": viewport_rows,
        "qa_matrix": qa_matrix,
        "cache_only": True,
        "runs_no_commands": True,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This runbook is an executable acceptance checklist. It does not itself prove visual QA, browser performance, or production motion completion.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the local LTG-14 browser QA runbook contract.")
    parser.add_argument("--json", action="store_true", help="Print the full runbook as JSON.")
    args = parser.parse_args()
    contract = build_runbook()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"motion_browser_qa_runbook: {contract['status']}")
        print(
            f"routes: {contract['route_count']}; viewports: {contract['viewport_count']}; "
            f"qa_matrix: {contract['qa_matrix_count']}"
        )
        print(
            "visual_qa_complete: false; browser_performance_verified: false; "
            "opens_no_browser: true; external_calls_triggered: false; does_not_execute_trades: true"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
