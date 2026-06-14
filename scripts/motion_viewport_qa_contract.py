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
REQUIRED_MOTION_PRODUCTION_STAGE_KEYS = {
    "motion_token_source_guardrails",
    "state_change_confirmation_cues",
    "chart_radar_delta_choreography",
    "reduced_motion_accessibility_review",
    "viewport_visual_qa_execution",
    "browser_performance_trace_execution",
    "local_artifact_review",
    "durable_ci_or_release_evidence",
    "production_promotion_review",
    "no_trade_no_action_boundary",
}
MOTION_PRODUCTION_STAGE_LABELS = {
    "motion_token_source_guardrails": "motion tokens and source guardrails are static and finite",
    "state_change_confirmation_cues": "state changes are visible without timers or recomputation",
    "chart_radar_delta_choreography": "chart and radar deltas need restrained visual choreography",
    "reduced_motion_accessibility_review": "reduced-motion accessibility review is required",
    "viewport_visual_qa_execution": "desktop and mobile viewport visual QA is required",
    "browser_performance_trace_execution": "browser performance trace is required",
    "local_artifact_review": "ignored local artifacts need explicit review",
    "durable_ci_or_release_evidence": "durable CI or release evidence is required",
    "production_promotion_review": "production motion promotion review is required",
    "no_trade_no_action_boundary": "motion must never imply or mutate trading action",
}
LOCAL_MOTION_STAGE_EVIDENCE_KEYS = {
    "motion_token_source_guardrails",
    "state_change_confirmation_cues",
    "chart_radar_delta_choreography",
    "no_trade_no_action_boundary",
}


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


def motion_production_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing_evidence = [
        "browser viewport visual QA",
        "browser performance trace",
        "reduced-motion review",
        "explicit local artifact review",
        "durable CI or release evidence",
        "production promotion approval",
    ]
    for stage_key in sorted(REQUIRED_MOTION_PRODUCTION_STAGE_KEYS):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": MOTION_PRODUCTION_STAGE_LABELS[stage_key],
                "scope": "motion_production_stage_scope_manifest",
                "current_status": (
                    "local_source_guard_ready_production_pending"
                    if stage_key in LOCAL_MOTION_STAGE_EVIDENCE_KEYS
                    else "direct_visual_or_performance_evidence_pending"
                ),
                "target_status": "production_motion_direct_evidence_required",
                "local_stage_evidence_present": stage_key in LOCAL_MOTION_STAGE_EVIDENCE_KEYS,
                "required_before_production_motion": True,
                "production_motion_complete": False,
                "visual_qa_complete": False,
                "browser_performance_verified": False,
                "browser_visual_qa_promoted": False,
                "browser_performance_promoted": False,
                "durable_ci_evidence_complete": False,
                "browser_runner_executed_by_contract": False,
                "local_artifact_reviewed_for_production": False,
                "reduced_motion_verified_by_browser": False,
                "changes_packet_values": False,
                "changes_strategy_action": False,
                "changes_price_or_position": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": missing_evidence,
            }
        )
    return rows


def build_contract() -> dict[str, Any]:
    styles = read_text(DESKTOP_SRC / "styles.css")
    app = read_text(DESKTOP_SRC / "App.tsx")
    page_state = read_text(DESKTOP_SRC / "components" / "PageStateBanner.tsx")
    packet_card = read_text(DESKTOP_SRC / "components" / "PacketCard.tsx")
    metric_grid = read_text(DESKTOP_SRC / "components" / "MetricGrid.tsx")
    task_panel = read_text(DESKTOP_SRC / "components" / "TaskStatusPanel.tsx")
    task_receipt = read_text(DESKTOP_SRC / "components" / "TaskLaunchReceipt.tsx")
    next_chart = read_text(DESKTOP_SRC / "components" / "NextSessionChart.tsx")
    candidate_radar = read_text(DESKTOP_SRC / "routes" / "CandidateRadar.tsx")
    package_json = read_text(ROOT / "desktop" / "package.json")
    runner_source = read_text(ROOT / "scripts" / "motion_browser_qa_runner.mjs")
    audited_text = "\n".join([styles, app, packet_card, metric_grid, page_state, task_panel, task_receipt, next_chart, candidate_radar])
    production_stage_rows = motion_production_stage_scope_rows()
    production_stage_keys = {str(item.get("stage_key") or "") for item in production_stage_rows}
    production_stage_scope_ready = (
        production_stage_keys == REQUIRED_MOTION_PRODUCTION_STAGE_KEYS
        and all(
            item.get("scope") == "motion_production_stage_scope_manifest"
            and item.get("target_status") == "production_motion_direct_evidence_required"
            and item.get("required_before_production_motion") is True
            and item.get("production_motion_complete") is False
            and item.get("visual_qa_complete") is False
            and item.get("browser_performance_verified") is False
            and item.get("browser_visual_qa_promoted") is False
            and item.get("browser_performance_promoted") is False
            and item.get("durable_ci_evidence_complete") is False
            and item.get("browser_runner_executed_by_contract") is False
            and item.get("local_artifact_reviewed_for_production") is False
            and item.get("reduced_motion_verified_by_browser") is False
            and item.get("changes_packet_values") is False
            and item.get("changes_strategy_action") is False
            and item.get("changes_price_or_position") is False
            and item.get("external_calls_triggered") is False
            and item.get("tushare_called") is False
            and item.get("deepseek_called") is False
            and item.get("github_called") is False
            and item.get("does_not_execute_trades") is True
            and item.get("does_not_modify_strategy_action") is True
            and item.get("contains_secret") is False
            and len(item.get("missing_evidence") or []) >= 6
            for item in production_stage_rows
        )
    )

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
            "visual_hierarchy_clarity_cue",
            'data-motion-purpose="visual_hierarchy_clarity"' in packet_card
            and 'data-motion-purpose="visual_hierarchy_clarity"' in metric_grid
            and "data-metric-tone" in metric_grid
            and '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"]::before' in styles
            and "@keyframes cc-hierarchy-focus" in styles
            and "pointer-events: none" in styles,
            "metric and packet surfaces expose a finite non-interactive hierarchy cue for dense-page scanability",
        ),
        row(
            "keynote_focus_sweep_cue",
            '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"]::after' in styles
            and "@keyframes cc-keynote-focus-sweep" in styles
            and "linear-gradient(105deg" in styles
            and '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"] > *' in styles
            and "z-index: 1" in styles
            and ".motion-surface[data-motion-purpose=\"visual_hierarchy_clarity\"]::after" in styles
            and "@media (prefers-reduced-motion: reduce)" in styles,
            "visual hierarchy surfaces add a finite keynote-style focus sweep while keeping child content above the cue and reduced-motion guarded",
        ),
        row(
            "packet_status_clarity_cue",
            'data-motion-scope="packet_status_clarity"' in packet_card
            and "function statusTone" in packet_card
            and "data-status-tone={tone}" in packet_card
            and 'StatusBadge label={status} tone={tone}' in packet_card
            and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="good"]' in styles
            and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="warn"]' in styles
            and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="bad"]' in styles,
            "packet cards map ready/pending/blocked status strings to matching good/warn/bad visual hierarchy cues",
        ),
        row(
            "mobile_responsive_motion_layout",
            "@media (max-width: 760px)" in styles
            and ".app-shell" in styles
            and "display: block;" in styles
            and ".sidebar nav" in styles
            and "overflow-x: auto;" in styles
            and ".content" in styles
            and "grid-template-columns: minmax(0, 1fr);" in styles
            and "repeat(auto-fit, minmax(118px, 1fr))" in styles,
            "mobile layout moves navigation out of the content column and keeps state clarity rails readable",
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
        row(
            "explicit_browser_runner_script_available",
            "command_center_3_motion_browser_qa_result.v1" in runner_source
            and "explicit_local_browser_visual_performance_run" in runner_source
            and "page.goto" in runner_source
            and ".stock_ming_3/motion_qa" in runner_source,
            "explicit runner can execute the pinned route/viewport matrix after local services are started",
        ),
        row(
            "motion_production_stage_scope_manifest_is_complete_and_pending",
            production_stage_scope_ready,
            "Motion production stages are listed as pending direct evidence while browser execution, visual QA promotion, performance promotion, durable evidence, packet/action mutation, external calls, and trade execution stay disabled.",
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
        "explicit_browser_runner_script_available": "command_center_3_motion_browser_qa_result.v1" in runner_source,
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
        "motion_production_stage_scope_rows": production_stage_rows,
        "motion_production_stage_scope_count": len(production_stage_rows),
        "motion_production_stage_scope_pending_count": sum(
            1
            for item in production_stage_rows
            if item.get("target_status") == "production_motion_direct_evidence_required"
            and item.get("production_motion_complete") is False
        ),
        "motion_production_stage_scope_keys": sorted(production_stage_keys),
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
