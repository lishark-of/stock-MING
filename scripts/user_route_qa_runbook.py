#!/usr/bin/env python3
"""Local ordinary-route browser QA runbook for Command Center 3.

This script does not open a browser, start FastAPI/Vite, call providers/models,
or execute trades. It pins the local browser QA route matrix for the ordinary
research workflow and verifies that the explicit runner keeps artifacts ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = ROOT / "scripts" / "user_route_qa_runner.mjs"
ARTIFACT_ROOT = ".stock_ming_3/user_route_qa"
LOCAL_VITE_BASE = "http://127.0.0.1:5173"
LOCAL_API_BASE = "http://127.0.0.1:8710"

QA_ROUTES = [
    {"route": "#home", "label": "Daily Command Center", "ltg": "LTG-10", "focus": "first-card readiness and next action"},
    {"route": "#candidates", "label": "Candidate Radar", "ltg": "LTG-13", "focus": "candidate controls and no-buy boundary"},
    {
        "route": "#marginEtf",
        "label": "ETF / Margin",
        "ltg": "LTG-10/LTG-12",
        "focus": "confirmed radar bridge, risk-budget rows, and no-margin boundary",
    },
    {"route": "#factor", "label": "Stock Quant Projection", "ltg": "LTG-03/LTG-10", "focus": "factor summary and provider gaps"},
    {"route": "#next", "label": "Next Session Map", "ltg": "LTG-08/LTG-10", "focus": "chart readability and no-action boundary"},
]

QA_VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "mobile", "width": 390, "height": 844},
]


def _read_text(path: Path) -> str:
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
    }


def build_runbook() -> dict[str, Any]:
    runner = _read_text(RUNNER_SCRIPT)
    runner_available = (
        RUNNER_SCRIPT.exists()
        and "command_center_3_user_route_qa_result.v1" in runner
        and "#home" in runner
        and "#candidates" in runner
        and "#marginEtf" in runner
        and "#factor" in runner
        and "#next" in runner
        and "typed_without_submit" in runner
        and "editable_visible_input_count" in runner
        and "typing_required" in runner
        and "typing_covered" in runner
        and "task_created_by_render_or_typing" in runner
        and "route_specific_check_passed" in runner
        and "margin_etf_confirmed_data_bridge_visible" in runner
        and 'aria-label="margin etf candidate radar confirmed data bridge"' in runner
        and ARTIFACT_ROOT in runner
        and "starts_no_servers: true" in runner
        and "local_urls_only: true" in runner
        and "external_calls_triggered: false" in runner
        and "does_not_execute_trades: true" in runner
        and "createRequire" in runner
        and "chromium.launch" in runner
        and "child_process" not in runner
        and "uvicorn" not in runner
        and "npm run dev" not in runner
        and "tushare_adapter" not in runner
        and "deepseek_adapter" not in runner
        and "api.github.com" not in runner
        and "place_order" not in runner
    )
    qa_matrix = [
        {
            "route": route["route"],
            "label": route["label"],
            "ltg": route["ltg"],
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "url": f"{LOCAL_VITE_BASE}/{route['route']}",
            "focus": route["focus"],
            "route_specific_check": "margin_etf_confirmed_data_bridge_visible"
            if route["route"] == "#marginEtf"
            else "generic_route_heading_visible",
            "visual_qa_complete": False,
            "typing_silence_verified": False,
        }
        for route in QA_ROUTES
        for viewport in QA_VIEWPORTS
    ]
    rows = [
        _row(
            "ordinary_route_matrix_pinned",
            "passed_static_policy",
            "home, candidates, marginEtf, factor, and next are pinned across desktop/mobile viewports",
        ),
        _row(
            "explicit_local_runner_available",
            "passed_static_policy" if runner_available else "blocked",
            "scripts/user_route_qa_runner.mjs can run the ordinary route matrix and write ignored local artifacts",
        ),
        _row(
            "render_and_typing_silence_check",
            "execution_pending",
            "runner compares /api/tasks count before and after route render plus actual safe typing on visible editable inputs without submit",
        ),
        _row(
            "visual_clarity_check",
            "execution_pending",
            "runner records h1, clipped primary text, disabled-button reason, audit-noise count, and screenshots",
        ),
        _row(
            "margin_etf_confirmed_data_bridge_check",
            "execution_pending",
            "runner verifies the rendered ETF/Margin route exposes the confirmed Candidate Radar bridge, same-result lineage labels, local links, and no provider/model/trade boundary",
        ),
        _row(
            "artifact_policy",
            "passed_static_policy",
            "screenshots and JSON report stay under ignored .stock_ming_3/user_route_qa and are not committed",
        ),
        _row(
            "production_boundary",
            "passed_static_policy",
            "User route QA is local usability evidence, not provider/model evidence, remote CI, or Streamlit retirement proof",
        ),
    ]
    blockers = [row["phase"] for row in rows if row["status"] == "blocked"]
    return {
        "schema_version": "command_center_3_user_route_qa_runbook.v1",
        "status": "user_route_qa_runbook_ready_execution_pending" if not blockers else "user_route_qa_runbook_blocked",
        "scope": "local_ordinary_route_browser_qa_runbook_not_browser_execution",
        "local_runbook_ready": not blockers,
        "runner_script": "scripts/user_route_qa_runner.mjs",
        "artifact_root": ARTIFACT_ROOT,
        "local_vite_base": LOCAL_VITE_BASE,
        "local_api_base": LOCAL_API_BASE,
        "route_count": len(QA_ROUTES),
        "viewport_count": len(QA_VIEWPORTS),
        "qa_matrix_count": len(qa_matrix),
        "qa_routes": QA_ROUTES,
        "qa_viewports": QA_VIEWPORTS,
        "qa_matrix": qa_matrix,
        "rows": rows,
        "blocking_phase_count": len(blockers),
        "blockers": blockers,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "execution_required_for_visual_qa": True,
        "visual_qa_complete": False,
        "typing_silence_verified": False,
        "production_replacement_complete": False,
        "streamlit_fallback_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "The runbook pins the ordinary route QA pass. Only the explicit runner creates local ignored browser artifacts.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the local Command Center ordinary route QA runbook.")
    parser.add_argument("--json", action="store_true", help="Print full JSON.")
    args = parser.parse_args()
    runbook = build_runbook()
    if args.json:
        print(json.dumps(runbook, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"user_route_qa_runbook: {runbook['status']}")
        print(
            "routes: {route_count}; viewports: {viewport_count}; qa_matrix: {qa_matrix_count}; "
            "visual_qa_complete: false; typing_silence_verified: false".format(**runbook)
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
