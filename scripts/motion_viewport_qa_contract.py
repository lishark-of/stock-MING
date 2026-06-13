#!/usr/bin/env python3
"""Static Command Center 3 motion viewport QA contract.

This script does not open a browser. It pins the routes, viewports, and motion
boundaries that a later browser run must verify, while still failing if the
local source contract for LTG-14 motion clarity regresses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SRC = ROOT / "desktop" / "src"

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


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def row(criterion: str, passed: bool, evidence: str, *, status: str | None = None) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "evidence": evidence,
    }


def build_contract() -> dict[str, Any]:
    styles = read_text(DESKTOP_SRC / "styles.css")
    app = read_text(DESKTOP_SRC / "App.tsx")
    page_state = read_text(DESKTOP_SRC / "components" / "PageStateBanner.tsx")
    task_panel = read_text(DESKTOP_SRC / "components" / "TaskStatusPanel.tsx")
    task_receipt = read_text(DESKTOP_SRC / "components" / "TaskLaunchReceipt.tsx")
    next_chart = read_text(DESKTOP_SRC / "components" / "NextSessionChart.tsx")
    candidate_radar = read_text(DESKTOP_SRC / "routes" / "CandidateRadar.tsx")
    package_json = read_text(ROOT / "desktop" / "package.json")
    audited_text = "\n".join([styles, app, page_state, task_panel, task_receipt, next_chart, candidate_radar])

    static_rows = [
        row(
            "motion_phase_confirm_keyframe",
            "@keyframes cc-phase-confirm" in styles,
            "finite state-change confirmation keyframe exists",
        ),
        row(
            "cache_refresh_motion_scope",
            'data-motion-scope="cache_refresh_clarity"' in page_state
            and 'data-motion-purpose="state_change_confirmation"' in page_state,
            "PageStateBanner marks loading/error/empty as state_change_confirmation",
        ),
        row(
            "task_phase_motion_scope",
            'data-motion-scope="task_phase_clarity"' in task_panel
            and 'data-motion-purpose="state_change_confirmation"' in task_panel,
            "TaskStatusPanel marks task phase changes as state_change_confirmation",
        ),
        row(
            "task_receipt_motion_scope",
            'data-motion-scope="task_receipt_clarity"' in task_receipt
            and 'data-motion-purpose="state_change_confirmation"' in task_receipt,
            "TaskLaunchReceipt marks task creation result as state_change_confirmation",
        ),
        row(
            "reduced_motion_contract",
            "@media (prefers-reduced-motion: reduce)" in styles and "transition-duration: 1ms !important" in styles,
            "reduced-motion media query keeps motion bounded",
        ),
        row(
            "layout_containment_contract",
            "contain: layout paint" in styles,
            "motion surfaces include layout/paint containment markers",
        ),
        row(
            "chart_motion_contract",
            "useReducedMotionPreference" in next_chart and "data-chart-state={chartMotionState}" in next_chart,
            "NextSessionChart exposes chart state and runtime reduced-motion handling",
        ),
        row(
            "candidate_radar_motion_contract",
            "data-radar-state={radarMotionState}" in candidate_radar,
            "CandidateRadar exposes cache/coverage/blocker/degraded state for visual grouping",
        ),
        row(
            "no_timer_or_raf_motion_loop",
            "setTimeout" not in audited_text and "requestAnimationFrame" not in audited_text,
            "audited motion files use no timer or RAF animation loop",
        ),
        row(
            "no_provider_or_trade_markers",
            not any(marker in audited_text for marker in ("tushare_adapter", "deepseek.chat", "gh api", "place_order", "submit_order")),
            "audited motion files contain no provider or trade invocation markers",
        ),
        row(
            "browser_runner_dependency_pending",
            "playwright" not in package_json.lower() and "puppeteer" not in package_json.lower(),
            "browser runner is not bundled; viewport QA remains a separate explicit run",
            status="pending",
        ),
    ]
    blockers = [item["criterion"] for item in static_rows if item["status"] == "blocked"]
    qa_matrix = [
        {
            "route": route["route"],
            "label": route["label"],
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": route["risk_focus"],
            "required_checks": [
                "no text overlap or clipped primary labels",
                "motion cue does not obscure warnings, freshness, or risk state",
                "no layout shift after state-change confirmation animation",
                "reduced-motion mode preserves readable state boundaries",
            ],
            "visual_qa_complete": False,
        }
        for route in QA_ROUTES
        for viewport in QA_VIEWPORTS
    ]
    return {
        "schema_version": "command_center_3_motion_viewport_qa_contract.v1",
        "status": "motion_viewport_qa_contract_ready_visual_run_pending" if not blockers else "motion_viewport_qa_contract_blocked",
        "scope": "local_static_contract_not_browser_execution",
        "ltg": "LTG-14",
        "contract_ready": not blockers,
        "production_motion_complete": False,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "browser_runner_bundled": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "routes": QA_ROUTES,
        "viewports": QA_VIEWPORTS,
        "qa_matrix": qa_matrix,
        "qa_matrix_count": len(qa_matrix),
        "static_rows": static_rows,
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "next_action": "Run a browser viewport and performance pass over this matrix before setting visual_qa_complete=true.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the static LTG-14 motion viewport QA contract.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"motion_viewport_qa_contract: {contract['status']}")
        print(f"routes: {len(contract['routes'])}; viewports: {len(contract['viewports'])}; qa_matrix: {contract['qa_matrix_count']}")
        print(
            "visual_qa_complete: false; browser_performance_verified: false; "
            "external_calls_triggered: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
