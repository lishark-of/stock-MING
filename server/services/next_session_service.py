from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import packet_service
from .task_service import create_task_record, update_task_status

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
MOTION_QA_ARTIFACT_ROOT = PROJECT_ROOT / ".stock_ming_3" / "motion_qa"
MOTION_BROWSER_QA_RUNNER_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runner.mjs"
NEXT_SESSION_ROUTE_SOURCE_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "NextSessionMap.tsx"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _local_ledger_boundary() -> dict[str, Any]:
    return {
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _activation_row(
    activation_key: str,
    status: str,
    *,
    local_ready: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    browser_visual_required: bool = False,
    performance_required: bool = False,
    parity_required: bool = False,
    ci_required: bool = False,
) -> dict[str, Any]:
    return {
        "activation_key": activation_key,
        "status": status,
        "local_ready": bool(local_ready),
        "production_ready": bool(production_ready),
        "production_blocker": not bool(production_ready),
        "browser_visual_required": bool(browser_visual_required),
        "performance_required": bool(performance_required),
        "parity_required": bool(parity_required),
        "ci_required": bool(ci_required),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
    }


def _safe_text(value: Any, limit: int = 160) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in ("traceback", "token", "api_key", "authorization", "bearer", "secret", "password")):
        return "redacted_local_browser_qa_text"
    return text[:limit]


def _relative_project_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _next_session_browser_qa_runbook_row(
    phase: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    required_before_completion: bool = True,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "required_before_completion": bool(required_before_completion),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
    }


def _next_session_browser_qa_runbook_contract() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    viewports = [
        {"name": "desktop", "width": 1440, "height": 960},
        {"name": "laptop", "width": 1280, "height": 832},
        {"name": "tablet", "width": 834, "height": 1112},
        {"name": "mobile", "width": 390, "height": 844},
    ]
    runner_source = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    route_source = _read_local_text(NEXT_SESSION_ROUTE_SOURCE_PATH)
    runner_available = (
        MOTION_BROWSER_QA_RUNNER_PATH.exists()
        and "#next" in runner_source
        and ".stock_ming_3/motion_qa" in runner_source
        and "starts_no_servers" in runner_source
        and "does_not_execute_trades" in runner_source
    )
    route_source_ready = (
        NEXT_SESSION_ROUTE_SOURCE_PATH.exists()
        and "NextSessionChart" in route_source
        and "next_session_replacement_activation_receipt" in route_source
        and "browser_visual_qa_done" in route_source
        and "browser_performance_trace_done" in route_source
        and "不运行浏览器" in route_source
    )
    rows = [
        _next_session_browser_qa_runbook_row(
            "next_session_browser_qa_runbook_ready",
            "passed_static_policy" if runner_available and route_source_ready else "blocked",
            passed=runner_available and route_source_ready,
            evidence="Shared motion runner covers #next and NextSessionMap exposes the replacement activation receipt.",
        ),
        _next_session_browser_qa_runbook_row(
            "next_route_source_ready",
            "passed_static_policy" if route_source_ready else "blocked",
            passed=route_source_ready,
            evidence="NextSessionMap.tsx displays chart contract, interaction audit, replacement blockers, and read-only boundaries.",
        ),
        _next_session_browser_qa_runbook_row(
            "default_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Default-motion browser pass is explicit and not run by GET cache or this runbook.",
            required_before_completion=False,
        ),
        _next_session_browser_qa_runbook_row(
            "reduced_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Reduced-motion browser pass is explicit and not run by GET cache or this runbook.",
            required_before_completion=False,
        ),
        _next_session_browser_qa_runbook_row(
            "streamlit_parity_and_performance_trace_pending",
            "execution_pending",
            passed=False,
            evidence="Legacy visual parity and performance trace still require explicit review before production replacement.",
            required_before_completion=False,
        ),
    ]
    blockers = [row["phase"] for row in rows if row["status"] == "blocked"]
    matrix_rows = [
        {
            "route": "#next",
            "label": "Next Session Map",
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": "ECharts readability, tooltip/click insight, replacement blockers, and no-action mutation boundary",
            "required_checks": [
                "ECharts plot, latest close, reference lines, and operation zones are readable",
                "hover/click insight does not compute strategy action",
                "replacement blockers remain visible without raw JSON",
                "mobile layout does not clip chart or blocker labels",
                "reduced-motion mode preserves state clarity",
            ],
            "visual_qa_complete": False,
            "browser_performance_trace_done": False,
        }
        for viewport in viewports
    ]
    local_ready = not blockers
    contract = {
        "schema_version": "next_session_browser_qa_runbook.v1",
        "status": "next_session_browser_qa_runbook_ready_execution_pending" if local_ready else "next_session_browser_qa_runbook_blocked",
        "scope": "local_next_session_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-08/LTG-14",
        "local_runbook_ready": local_ready,
        "runner_available": runner_available,
        "next_route_source_ready": route_source_ready,
        "shared_runner_script": "scripts/motion_browser_qa_runner.mjs",
        "next_route": "#next",
        "artifact_root": ".stock_ming_3/motion_qa",
        "route_count": 1,
        "viewport_count": len(viewports),
        "qa_matrix_count": len(matrix_rows),
        "row_count": len(rows),
        "blocking_phase_count": len(blockers),
        "blockers": blockers,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "visual_qa_complete": False,
        "browser_performance_trace_done": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "note": "This runbook prepares targeted #next browser QA. It is not browser execution, Streamlit parity, performance promotion, or production replacement.",
    }
    return contract, rows, matrix_rows


def _read_next_session_browser_qa_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _next_session_browser_qa_evidence_row(report: Mapping[str, Any], row: Mapping[str, Any], report_path: Path) -> dict[str, Any]:
    transition_observed = row.get("route_transition_observed_ms")
    transition_budget = row.get("route_transition_budget_ms") or _as_dict(report.get("performance_budgets")).get(
        "route_transition_observed_ms"
    )
    try:
        transition_within_budget = float(transition_observed) <= float(transition_budget)
    except Exception:
        transition_within_budget = False
    row_status = str(row.get("status") or "unknown")
    long_task_count = int(row.get("long_task_over_50ms_count") or 0)
    clipped_count = int(row.get("clipped_count") or 0)
    offscreen_count = int(row.get("offscreen_count") or 0)
    performance_trace_complete = row.get("performance_trace_complete") is True
    visual_complete = row.get("visual_qa_complete") is True and row_status == "passed"
    performance_passed = performance_trace_complete and transition_within_budget and long_task_count == 0
    return {
        "run_id": report.get("run_id") or report_path.parent.name,
        "generated_at": report.get("generated_at"),
        "reduced_motion": report.get("reduced_motion") is True,
        "route": str(row.get("route") or ""),
        "label": str(row.get("label") or "Next Session Map"),
        "viewport": str(row.get("viewport") or ""),
        "width": row.get("width"),
        "height": row.get("height"),
        "status": row_status,
        "visual_qa_complete": visual_complete,
        "performance_trace_complete": performance_trace_complete,
        "performance_passed": performance_passed,
        "route_transition_observed_ms": transition_observed,
        "route_transition_budget_ms": transition_budget,
        "long_task_over_50ms_count": long_task_count,
        "largest_motion_layout_shift": row.get("largest_motion_layout_shift"),
        "clipped_count": clipped_count,
        "offscreen_count": offscreen_count,
        "review_required": row_status != "passed" or not visual_complete or not performance_passed,
        "artifact_report_path": _relative_project_path(report_path),
        "screenshot_path": _safe_text(row.get("screenshot_path"), limit=240),
        "reads_local_artifact_only": True,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
    }


def _next_session_browser_qa_evidence_summary() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_paths = (
        sorted(MOTION_QA_ARTIFACT_ROOT.glob("*/motion_browser_qa_report.json"))
        if MOTION_QA_ARTIFACT_ROOT.exists()
        else []
    )
    next_rows: list[dict[str, Any]] = []
    scanned_report_count = 0
    valid_report_count = 0
    next_report_count = 0
    latest_report_path: str | None = None
    latest_run_id: str | None = None
    latest_generated_at: Any = None
    for path in report_paths[-20:]:
        scanned_report_count += 1
        report = _read_next_session_browser_qa_report(path)
        if not report:
            continue
        valid_report = (
            report.get("schema_version") == "command_center_3_motion_browser_qa_result.v1"
            and report.get("scope") == "explicit_local_browser_visual_performance_run"
            and report.get("local_urls_only") is True
            and report.get("starts_no_servers") is True
            and report.get("external_calls_triggered") is False
            and report.get("tushare_called") is False
            and report.get("deepseek_called") is False
            and report.get("github_called") is False
            and report.get("does_not_execute_trades") is True
            and report.get("does_not_modify_strategy_action") is True
        )
        if not valid_report:
            continue
        valid_report_count += 1
        report_next_rows = [
            row
            for row in _as_list(report.get("rows"))
            if isinstance(row, Mapping) and str(row.get("route") or "") == "#next"
        ]
        if not report_next_rows:
            continue
        next_report_count += 1
        latest_report_path = _relative_project_path(path)
        latest_run_id = str(report.get("run_id") or path.parent.name)
        latest_generated_at = report.get("generated_at")
        next_rows.extend(_next_session_browser_qa_evidence_row(report, row, path) for row in report_next_rows)

    next_rows = next_rows[-16:]
    row_count = len(next_rows)
    review_required_count = sum(1 for row in next_rows if row.get("review_required") is True)
    visual_passed_count = sum(1 for row in next_rows if row.get("visual_qa_complete") is True)
    performance_passed_count = sum(1 for row in next_rows if row.get("performance_passed") is True)
    required_viewports = {"desktop", "laptop", "tablet", "mobile"}
    default_motion_viewports = {
        str(row.get("viewport") or "")
        for row in next_rows
        if row.get("reduced_motion") is False and row.get("review_required") is False
    }
    reduced_motion_viewports = {
        str(row.get("viewport") or "")
        for row in next_rows
        if row.get("reduced_motion") is True and row.get("review_required") is False
    }
    default_motion_passed = required_viewports.issubset(default_motion_viewports)
    reduced_motion_passed = required_viewports.issubset(reduced_motion_viewports)
    motion_viewport_coverage_complete = default_motion_passed and reduced_motion_passed
    local_evidence_found = row_count > 0
    visual_passed = local_evidence_found and visual_passed_count == row_count and review_required_count == 0
    performance_passed = local_evidence_found and performance_passed_count == row_count and review_required_count == 0
    evidence_ready = visual_passed and performance_passed and motion_viewport_coverage_complete
    status = (
        "next_session_browser_qa_evidence_passed_local_artifact"
        if evidence_ready
        else "next_session_browser_qa_evidence_review_required_local_artifact"
        if local_evidence_found
        else "next_session_browser_qa_evidence_pending"
    )
    summary = {
        "schema_version": "next_session_browser_qa_evidence.v1",
        "status": status,
        "scope": "local_next_session_browser_qa_evidence_reader_no_browser_execution",
        "ltg": "LTG-08/LTG-14",
        "artifact_root": ".stock_ming_3/motion_qa",
        "local_browser_qa_evidence_found": local_evidence_found,
        "scanned_report_count": scanned_report_count,
        "valid_report_count": valid_report_count,
        "next_report_count": next_report_count,
        "next_route": "#next",
        "next_viewport_row_count": row_count,
        "review_required_count": review_required_count,
        "visual_passed_count": visual_passed_count,
        "performance_passed_count": performance_passed_count,
        "default_motion_passed": default_motion_passed,
        "reduced_motion_passed": reduced_motion_passed,
        "required_viewports": sorted(required_viewports),
        "default_motion_viewports": sorted(viewport for viewport in default_motion_viewports if viewport),
        "reduced_motion_viewports": sorted(viewport for viewport in reduced_motion_viewports if viewport),
        "missing_default_motion_viewports": sorted(required_viewports - default_motion_viewports),
        "missing_reduced_motion_viewports": sorted(required_viewports - reduced_motion_viewports),
        "motion_viewport_coverage_complete": motion_viewport_coverage_complete,
        "next_browser_qa_evidence_ready": evidence_ready,
        "next_visual_qa_evidence_passed": visual_passed,
        "next_browser_performance_evidence_passed": performance_passed,
        "browser_visual_qa_done": visual_passed,
        "browser_performance_trace_done": performance_passed,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "latest_report_path": latest_report_path,
        "latest_run_id": latest_run_id,
        "latest_generated_at": latest_generated_at,
        "row_count": row_count,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "note": "This reads ignored local motion browser QA reports for #next only. It does not open a browser, write artifacts, prove Streamlit parity, or mark production replacement complete.",
    }
    return summary, next_rows


def _next_session_browser_qa_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    blocks_review: bool = False,
    blocks_production: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "blocks_review": bool(blocks_review and not passed),
        "blocks_production": bool(blocks_production),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
    }


def _next_session_browser_qa_review_contract(
    evidence_summary: Mapping[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    viewport_names = {str(row.get("viewport") or "") for row in evidence_rows}
    required_viewports = {"desktop", "laptop", "tablet", "mobile"}
    evidence_found = evidence_summary.get("local_browser_qa_evidence_found") is True
    review_rows = [
        _next_session_browser_qa_review_row(
            "explicit_post_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            passed=explicit_review,
            evidence="POST /api/next-session/browser-qa-review creates the review record; GET cache only previews local evidence.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "next_route_evidence_available",
            "passed" if evidence_found else "pending_local_report",
            passed=evidence_found,
            evidence="next_session_browser_qa_evidence_summary found ignored local runner rows for #next.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "next_viewport_matrix_complete",
            "passed" if required_viewports.issubset(viewport_names) else "pending_viewports",
            passed=required_viewports.issubset(viewport_names),
            evidence="desktop/laptop/tablet/mobile #next rows must all be present in local runner evidence.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "visual_evidence_passed",
            "passed" if evidence_summary.get("next_visual_qa_evidence_passed") is True else "pending_visual_review",
            passed=evidence_summary.get("next_visual_qa_evidence_passed") is True,
            evidence="All #next route rows must report visual_qa_complete with no clipped/offscreen blockers.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "performance_evidence_passed",
            "passed" if evidence_summary.get("next_browser_performance_evidence_passed") is True else "pending_performance_review",
            passed=evidence_summary.get("next_browser_performance_evidence_passed") is True,
            evidence="All #next route rows must include performance traces within local budgets and no long tasks.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "default_and_reduced_motion_coverage",
            "passed"
            if evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True
            else "pending_reduced_or_default_motion",
            passed=evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True,
            evidence="Both default-motion and reduced-motion #next route passes are required before local review can be ready.",
            blocks_review=True,
        ),
        _next_session_browser_qa_review_row(
            "streamlit_parity_stays_pending",
            "passed",
            passed=True,
            evidence="Browser QA evidence cannot replace explicit Streamlit visual parity review.",
            blocks_review=False,
            blocks_production=True,
        ),
        _next_session_browser_qa_review_row(
            "production_replacement_stays_blocked",
            "passed",
            passed=True,
            evidence="Local browser QA review cannot promote ECharts production replacement without durable parity/performance evidence.",
            blocks_review=False,
            blocks_production=True,
        ),
    ]
    blocking_review_rows = [row for row in review_rows if row.get("blocks_review") is True]
    local_review_ready = explicit_review and not blocking_review_rows
    status = "next_session_browser_qa_review_ready_local_artifact" if local_review_ready else "next_session_browser_qa_review_pending"
    return {
        "schema_version": "next_session_browser_qa_review.v1",
        "status": status,
        "scope": "button_gated_local_next_session_browser_qa_review_no_browser_execution",
        "ltg": "LTG-08/LTG-14",
        "explicit_review_task_done": bool(explicit_review),
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "local_browser_qa_review_ready": local_review_ready,
        "local_browser_qa_evidence_found": evidence_found,
        "next_route": "#next",
        "required_viewports": sorted(required_viewports),
        "observed_viewports": sorted(viewport for viewport in viewport_names if viewport),
        "review_required_count": evidence_summary.get("review_required_count", 0),
        "evidence_row_count": len(evidence_rows),
        "review_row_count": len(review_rows),
        "blocking_review_count": len(blocking_review_rows),
        "blocking_review_keys": [str(row.get("criterion")) for row in blocking_review_rows],
        "default_motion_passed": evidence_summary.get("default_motion_passed") is True,
        "reduced_motion_passed": evidence_summary.get("reduced_motion_passed") is True,
        "motion_viewport_coverage_complete": evidence_summary.get("motion_viewport_coverage_complete") is True,
        "missing_default_motion_viewports": evidence_summary.get("missing_default_motion_viewports", []),
        "missing_reduced_motion_viewports": evidence_summary.get("missing_reduced_motion_viewports", []),
        "next_visual_qa_evidence_passed": evidence_summary.get("next_visual_qa_evidence_passed") is True,
        "next_browser_performance_evidence_passed": evidence_summary.get("next_browser_performance_evidence_passed") is True,
        "rows": review_rows,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "browser_visual_qa_done": evidence_summary.get("next_visual_qa_evidence_passed") is True,
        "browser_performance_trace_done": evidence_summary.get("next_browser_performance_evidence_passed") is True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "note": "This review promotes local #next browser QA evidence only to a button-gated local review state. It does not execute browser QA, prove Streamlit parity, or complete production replacement.",
    }


def _next_session_replacement_activation_receipt(packet: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chart = _as_dict(packet.get("chart_payload"))
    chart_summary = _as_dict(packet.get("chart_summary"))
    chart_contract = _as_dict(chart.get("chart_contract"))
    interaction_audit = _as_dict(chart.get("interaction_readiness_audit"))
    chart_maturity = _as_dict(chart.get("chart_maturity"))
    reference_rows = [row for row in _as_list(chart.get("reference_line_rows")) if isinstance(row, dict)]
    zone_rows = [row for row in _as_list(chart.get("zone_interaction_rows")) if isinstance(row, dict)]
    position_conflict = _as_dict(chart.get("position_conflict"))
    data_trust = _as_dict(chart.get("data_trust_summary"))
    exact_payload_ready = (
        chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and chart.get("uses_real_daily_close") is True
        and chart_summary.get("has_drawable_data") is True
        and chart_maturity.get("status") == "ready"
    )
    interaction_ready = (
        interaction_audit.get("status") == "interaction_contract_ready_parity_pending"
        and int(interaction_audit.get("blocking_count") or 0) == 0
    )
    read_only_ready = (
        chart_contract.get("cache_only") is not False
        and chart_contract.get("external_calls_triggered") is not True
        and chart_contract.get("tushare_called") is not True
        and chart_contract.get("deepseek_called") is not True
        and chart_contract.get("github_called") is not True
        and chart_contract.get("does_not_execute_trades") is not False
        and chart_contract.get("frontend_computes_trade_action") is not True
        and chart_contract.get("does_not_modify_action") is not False
        and chart_contract.get("does_not_modify_operation_zones") is not False
    )
    reference_zone_ready = bool(reference_rows) and bool(zone_rows) and all(
        row.get("frontend_mutable") is False for row in reference_rows + zone_rows
    )
    context_ready = bool(position_conflict) and bool(_as_list(data_trust.get("facts"))) and bool(chart.get("deepseek_status"))
    streamlit_parity_complete = interaction_audit.get("streamlit_parity_complete") is True
    production_replacement_complete = interaction_audit.get("production_replacement_complete") is True
    browser_visual_qa_done = False
    browser_performance_trace_done = False
    durable_ci_evidence_complete = False
    rows = [
        _activation_row(
            "exact_echarts_payload_ready",
            "passed" if exact_payload_ready else "blocked",
            local_ready=exact_payload_ready,
            production_ready=exact_payload_ready,
            evidence=(
                f"status={chart.get('status')}; exact={chart.get('is_exact_next_session_packet')}; "
                f"real_close={chart.get('uses_real_daily_close')}; maturity={chart_maturity.get('status')}"
            ),
            next_action="Keep exact command_center_next_session_projection_packet payload available before parity review.",
        ),
        _activation_row(
            "interaction_readiness_ready",
            "passed" if interaction_ready else "blocked",
            local_ready=interaction_ready,
            production_ready=interaction_ready,
            evidence=f"status={interaction_audit.get('status')}; blocking_count={interaction_audit.get('blocking_count')}",
            next_action="Maintain hover/click/source/guardrail rows while parity remains pending.",
        ),
        _activation_row(
            "reference_zone_context_visible",
            "passed" if reference_zone_ready and context_ready else "blocked",
            local_ready=reference_zone_ready and context_ready,
            production_ready=reference_zone_ready and context_ready,
            evidence=(
                f"reference_rows={len(reference_rows)}; zone_rows={len(zone_rows)}; "
                f"position_conflict={bool(position_conflict)}; data_trust_facts={len(_as_list(data_trust.get('facts')))}"
            ),
            next_action="Keep reference sources, zone guardrails, position conflict, data trust, and DeepSeek status visible.",
        ),
        _activation_row(
            "frontend_read_only_boundary",
            "passed" if read_only_ready else "blocked",
            local_ready=read_only_ready,
            production_ready=read_only_ready,
            evidence="chart_contract keeps cache-only/no-provider/no-action/no-operation-zone-mutation flags.",
            next_action="Do not compute action, mutate prices/positions, or rewrite operation_zones in React/ECharts.",
        ),
        _activation_row(
            "streamlit_parity_review_required",
            "pending_streamlit_parity_review",
            local_ready=False,
            production_ready=streamlit_parity_complete,
            parity_required=True,
            evidence=f"streamlit_parity_complete={streamlit_parity_complete}",
            next_action="Run explicit Streamlit parity review before claiming ECharts production replacement.",
        ),
        _activation_row(
            "browser_visual_qa_required",
            "pending_browser_visual_qa",
            local_ready=False,
            production_ready=browser_visual_qa_done,
            browser_visual_required=True,
            evidence=f"browser_visual_qa_done={browser_visual_qa_done}",
            next_action="Run browser viewport QA over NextSessionMap and chart interactions.",
        ),
        _activation_row(
            "browser_performance_trace_required",
            "pending_browser_performance_trace",
            local_ready=False,
            production_ready=browser_performance_trace_done,
            performance_required=True,
            evidence=f"browser_performance_trace_done={browser_performance_trace_done}",
            next_action="Capture route/chart update performance trace before production replacement promotion.",
        ),
        _activation_row(
            "durable_ci_or_release_evidence_required",
            "pending_durable_evidence",
            local_ready=False,
            production_ready=durable_ci_evidence_complete,
            ci_required=True,
            evidence=f"durable_ci_evidence_complete={durable_ci_evidence_complete}",
            next_action="Keep local browser artifacts separate from durable CI or release evidence.",
        ),
        _activation_row(
            "production_replacement_stays_blocked",
            "passed" if not production_replacement_complete else "blocked",
            local_ready=True,
            production_ready=not production_replacement_complete,
            evidence=f"production_replacement_complete={production_replacement_complete}",
            next_action="Only flip production replacement after parity, visual QA, performance trace, and durable evidence are direct.",
        ),
        _activation_row(
            "no_external_trade_or_action_side_effects",
            "passed",
            local_ready=True,
            production_ready=True,
            evidence="GET cache receipt is local and visual-only.",
            next_action="Keep Tushare/DeepSeek/GitHub and real trading out of GET/render paths.",
        ),
    ]
    local_blockers = [
        row["activation_key"]
        for row in rows
        if not row["local_ready"]
        and row["activation_key"]
        in {
            "exact_echarts_payload_ready",
            "interaction_readiness_ready",
            "reference_zone_context_visible",
            "frontend_read_only_boundary",
        }
    ]
    production_blockers = [str(row["activation_key"]) for row in rows if row["production_blocker"]]
    missing_evidence_items = [
        "exact_echarts_payload" if not exact_payload_ready else "",
        "streamlit_parity_review" if not streamlit_parity_complete else "",
        "browser_visual_qa" if not browser_visual_qa_done else "",
        "browser_performance_trace" if not browser_performance_trace_done else "",
        "durable_ci_or_release_evidence" if not durable_ci_evidence_complete else "",
    ]
    missing_evidence_items = [item for item in missing_evidence_items if item]
    local_activation_ready = not local_blockers
    receipt = {
        "schema_version": "next_session_replacement_activation_receipt.v1",
        "status": "next_session_activation_receipt_ready_replacement_blocked"
        if local_activation_ready
        else "next_session_activation_receipt_blocked",
        "scope": "local_next_session_replacement_activation_receipt_no_browser_no_provider",
        "ltg": "LTG-08",
        "local_activation_receipt_ready": local_activation_ready,
        "production_replacement_complete": False,
        "streamlit_parity_complete": streamlit_parity_complete,
        "browser_visual_qa_done": browser_visual_qa_done,
        "browser_performance_trace_done": browser_performance_trace_done,
        "durable_ci_evidence_complete": durable_ci_evidence_complete,
        "frontend_render_only": True,
        "allowed_next_step": "explicit_streamlit_parity_browser_visual_performance_review_then_replacement_promotion",
        "not_allowed_next_steps": [
            "treat_interaction_readiness_as_streamlit_parity",
            "treat_echarts_payload_as_browser_visual_qa",
            "treat_local_render_as_performance_trace",
            "mark_production_replacement_without_durable_evidence",
            "use_frontend_to_compute_action_or_modify_operation_zones",
        ],
        "missing_evidence_items": missing_evidence_items,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "missing_evidence_count": len(missing_evidence_items),
        "production_blockers": production_blockers,
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
        "does_not_modify_operation_zones": True,
        "note": "This receipt sequences LTG-08 replacement acceptance. It does not run browser QA, call providers, create CI evidence, or complete ECharts production replacement.",
    }
    return receipt, rows


def read_next_session_cache() -> dict[str, Any]:
    packet = dict(packet_service.build_next_session_cache())
    activation_receipt, activation_rows = _next_session_replacement_activation_receipt(packet)
    (
        browser_qa_runbook,
        browser_qa_runbook_rows,
        browser_qa_matrix_rows,
    ) = _next_session_browser_qa_runbook_contract()
    browser_qa_evidence, browser_qa_evidence_rows = _next_session_browser_qa_evidence_summary()
    existing_browser_qa_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    if existing_browser_qa_review.get("explicit_review_task_done") is True:
        browser_qa_review = existing_browser_qa_review
    else:
        browser_qa_review = _next_session_browser_qa_review_contract(browser_qa_evidence, browser_qa_evidence_rows)
    packet["next_session_replacement_activation_receipt"] = activation_receipt
    packet["next_session_replacement_activation_rows"] = activation_rows
    packet["next_session_browser_qa_runbook_contract"] = browser_qa_runbook
    packet["next_session_browser_qa_runbook_rows"] = browser_qa_runbook_rows
    packet["next_session_browser_qa_matrix_rows"] = browser_qa_matrix_rows
    packet["next_session_browser_qa_evidence_summary"] = browser_qa_evidence
    packet["next_session_browser_qa_evidence_rows"] = browser_qa_evidence_rows
    packet["next_session_browser_qa_review_contract"] = browser_qa_review
    packet["next_session_browser_qa_review_rows"] = _as_list(browser_qa_review.get("rows"))
    packet["next_session_activation_receipt_ready"] = activation_receipt["local_activation_receipt_ready"]
    packet["next_session_activation_production_blocker_count"] = activation_receipt["production_blocker_count"]
    packet["next_session_activation_missing_evidence_count"] = activation_receipt["missing_evidence_count"]
    packet["next_session_browser_qa_runbook_ready"] = browser_qa_runbook["local_runbook_ready"]
    packet["next_session_browser_qa_evidence_ready"] = browser_qa_evidence["next_browser_qa_evidence_ready"]
    packet["next_session_browser_qa_review_ready"] = browser_qa_review["local_browser_qa_review_ready"]
    packet["next_session_browser_qa_review_blocking_count"] = browser_qa_review["blocking_review_count"]
    packet.setdefault("call_ledger", _next_session_cache_call_ledger(packet, _now_iso()))
    packet.setdefault(
        "warnings",
        [
            "GET /api/next-session/cache 只读取本地次日图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
            " next_session_replacement_activation_receipt 只是替代验收路径，不运行浏览器、不证明生产替代完成。"
        ],
    )
    return packet


def _next_session_browser_qa_review_call_ledger(review_contract: Mapping[str, Any], now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_next_session_browser_qa_review",
            "request_params_safe": {
                "review_scope": "next_session_browser_qa_local_artifact",
                "next_route": "#next",
                "external_sources_allowed": False,
                "opens_no_browser": True,
                "writes_no_artifacts": True,
                "production_replacement_complete": False,
            },
            "row_count": review_contract.get("review_row_count", 0),
            "data_date": review_contract.get("reviewed_at"),
            "local_fetched_at": now,
            "call_status": review_contract.get("status"),
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def run_next_session_browser_qa_review_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_next_session_browser_qa_review",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_browser_qa_review_queued",
        warnings=[
            "次日图谱 browser QA review 只读取本地 ignored runner 报告；不会打开浏览器、不会启动服务、不会调用 Tushare/DeepSeek/GitHub。",
            "review 结果只代表本地 artifact 审查状态；不代表 Streamlit parity、durable CI evidence 或 production ECharts replacement。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_next_session_browser_qa_evidence",
    )
    packet = read_next_session_cache()
    evidence_summary = _as_dict(packet.get("next_session_browser_qa_evidence_summary"))
    evidence_rows = [row for row in _as_list(packet.get("next_session_browser_qa_evidence_rows")) if isinstance(row, dict)]
    reviewed_at = _now_iso()
    review_contract = _next_session_browser_qa_review_contract(
        evidence_summary,
        evidence_rows,
        explicit_review=True,
        task_id=task["task_id"],
        reviewed_at=reviewed_at,
    )
    ledger = _next_session_browser_qa_review_call_ledger(review_contract, reviewed_at)
    packet["task_id"] = task["task_id"]
    packet["next_session_browser_qa_review_completed_at"] = reviewed_at
    packet["next_session_browser_qa_review_contract"] = review_contract
    packet["next_session_browser_qa_review_rows"] = review_contract["rows"]
    packet["next_session_browser_qa_review_ready"] = review_contract["local_browser_qa_review_ready"]
    packet["next_session_browser_qa_review_blocking_count"] = review_contract["blocking_review_count"]
    packet["task_call_ledger"] = ledger
    if _persistable_next_session_packet(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_next_session_projection_packet", packet)
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="next_session_browser_qa_review_ready"
        if review_contract["local_browser_qa_review_ready"]
        else "next_session_browser_qa_review_pending",
        call_ledger=ledger,
        warning="next_session_browser_qa_review_completed_no_external_call",
    ) or task


def _safe_error_message(exc: Exception) -> str:
    text = str(exc or "").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in ("traceback", "token", "api_key", "authorization", "bearer", "secret", "password")):
        return "local next-session cache pipeline failed"
    return text[:500] or "local next-session cache pipeline failed"


def _chart_payload_row_count(packet: dict[str, Any]) -> int:
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), dict) else {}
    total = 0
    for key in ("historical_points", "reference_lines", "operation_zones"):
        value = chart.get(key)
        if isinstance(value, list):
            total += len(value)
    for item in chart.get("scenario_series") or []:
        if isinstance(item, dict) and isinstance(item.get("points"), list):
            total += len(item["points"])
    return total


def _cache_call_status(packet: dict[str, Any]) -> str:
    if packet.get("status") == "cache_missing":
        return "cache_missing"
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), dict) else {}
    if chart.get("is_exact_next_session_packet") is True:
        return "exact_cache_read"
    return "cache_read"


def _next_session_data_date(packet: dict[str, Any]) -> Any:
    if packet.get("trade_date") or packet.get("base_date"):
        return packet.get("trade_date") or packet.get("base_date")
    chart = packet.get("chart_payload")
    if isinstance(chart, dict):
        return chart.get("base_date")
    return None


def _next_session_cache_call_ledger(packet: dict[str, Any], now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_next_session_cache",
            "request_params_safe": {
                "packet_key": packet.get("packet_key"),
                "status": packet.get("status"),
                "cache_source": packet.get("cache_source"),
                "chart_status": (packet.get("chart_payload") or {}).get("status") if isinstance(packet.get("chart_payload"), dict) else None,
            },
            "row_count": _chart_payload_row_count(packet),
            "data_date": _next_session_data_date(packet),
            "local_fetched_at": now,
            "call_status": _cache_call_status(packet),
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _persistable_next_session_packet(packet: dict[str, Any]) -> bool:
    return packet.get("packet_key") == "command_center_next_session_projection_packet" and packet.get("status") != "cache_missing"


def create_next_session_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "build_next_session_projection",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_cache_pipeline_queued",
        warnings=[
            "Command Center 3.0 当前只执行本地 cache pipeline；不调用 Tushare、DeepSeek、GitHub。",
            "任务只读取并持久化已有次日图谱 packet，不修改 strategy action 或 operation_zones。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="reading_next_session_cache")
    now = _now_iso()
    try:
        packet = dict(read_next_session_cache())
        packet["task_call_ledger"] = _next_session_cache_call_ledger(packet, now)
        packet["does_not_modify_action"] = True
        packet["does_not_modify_operation_zones"] = True
        packet["external_calls_triggered"] = False
        packet["tushare_called"] = False
        packet["deepseek_called"] = False
        packet["github_called"] = False
        call_ledger = list(packet["task_call_ledger"])
        update_task_status(task["task_id"], status="running", progress=0.65, current_step="evaluating_next_session_cache", call_ledger=call_ledger)
        if _persistable_next_session_packet(packet):
            SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_next_session_projection_packet", packet)
            return update_task_status(
                task["task_id"],
                status="success",
                progress=1.0,
                current_step="next_session_cache_written_to_sqlite",
                call_ledger=call_ledger,
            ) or task
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="next_session_cache_missing_no_packet_written",
            call_ledger=call_ledger,
            warning="精确次日操作图谱 cache 缺失；任务没有写入 SQLite packet。",
        ) or task
    except Exception as exc:
        failed_ledger = [
            {
                "api": "local_next_session_cache",
                "request_params_safe": {},
                "row_count": 0,
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "failed",
                "error_message_safe": _safe_error_message(exc),
                **_local_ledger_boundary(),
            }
        ]
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="next_session_cache_pipeline_failed",
            error_message_safe=_safe_error_message(exc),
            call_ledger=failed_ledger,
        ) or task
