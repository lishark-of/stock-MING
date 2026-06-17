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
NEXT_SESSION_BROWSER_QA_REVIEW_PACKET_KEY = "command_center_next_session_browser_qa_review_packet"
NEXT_SESSION_DURABLE_EVIDENCE_SCHEMA_VERSION = "next_session_durable_evidence_recipe.v1"
NEXT_SESSION_DURABLE_EVIDENCE_KEYS = (
    "cache_render_boundary_visible",
    "exact_echarts_payload_visible",
    "interaction_contract_visible",
    "legacy_parity_recipe_visible",
    "browser_qa_runbook_visible",
    "local_browser_qa_review_visible",
    "streamlit_reference_capture_required",
    "feature_by_feature_parity_required",
    "hover_click_parity_required",
    "durable_browser_visual_performance_evidence_required",
    "durable_ci_release_evidence_required",
    "production_replacement_review_required",
    "no_provider_trade_action_secret_boundary",
)
NEXT_SESSION_DURABLE_EVIDENCE_LABELS = {
    "cache_render_boundary_visible": "Cache/render boundary is visible",
    "exact_echarts_payload_visible": "Exact ECharts payload is visible",
    "interaction_contract_visible": "Interaction contract is visible",
    "legacy_parity_recipe_visible": "Legacy parity recipe is visible",
    "browser_qa_runbook_visible": "Browser QA runbook is visible",
    "local_browser_qa_review_visible": "Local browser QA review is visible",
    "streamlit_reference_capture_required": "Streamlit reference capture is required",
    "feature_by_feature_parity_required": "Feature-by-feature parity is required",
    "hover_click_parity_required": "Hover/click parity is required",
    "durable_browser_visual_performance_evidence_required": "Durable browser visual/performance evidence is required",
    "durable_ci_release_evidence_required": "Durable CI or release evidence is required",
    "production_replacement_review_required": "Production replacement review is required",
    "no_provider_trade_action_secret_boundary": "No provider/trade/action/secret boundary is preserved",
}
NEXT_SESSION_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION = "next_session_production_stage_scope_manifest.v1"
NEXT_SESSION_PRODUCTION_STAGE_KEYS = (
    "exact_cache_payload_contract",
    "interaction_hover_click_contract",
    "streamlit_parity_review",
    "browser_visual_qa",
    "browser_performance_trace",
    "reduced_motion_accessibility_qa",
    "durable_ci_release_evidence",
    "production_replacement_promotion",
)
NEXT_SESSION_PRODUCTION_STAGE_LABELS = {
    "exact_cache_payload_contract": "exact cache payload and chart contract",
    "interaction_hover_click_contract": "hover and click interaction contract",
    "streamlit_parity_review": "legacy Streamlit parity review",
    "browser_visual_qa": "browser visual QA across viewports",
    "browser_performance_trace": "browser performance trace",
    "reduced_motion_accessibility_qa": "reduced-motion and accessibility QA",
    "durable_ci_release_evidence": "durable CI or release evidence",
    "production_replacement_promotion": "production replacement promotion review",
}


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
    blocking_review_rows = [
        row for row in review_rows if row.get("blocks_review") is True and row.get("passed") is not True
    ]
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


def _safe_persisted_browser_qa_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    safe = (
        review.get("schema_version") == "next_session_browser_qa_review.v1"
        and review.get("scope") == "button_gated_local_next_session_browser_qa_review_no_browser_execution"
        and review.get("explicit_review_task_done") is True
        and review.get("local_browser_qa_review_ready") is True
        and review.get("production_replacement_complete") is False
        and review.get("streamlit_parity_complete") is False
        and review.get("opens_no_browser") is True
        and review.get("starts_no_servers") is True
        and review.get("writes_no_artifacts") is True
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("does_not_modify_operation_zones") is True
    )
    return review if safe else {}


def _read_next_session_browser_qa_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(NEXT_SESSION_BROWSER_QA_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_browser_qa_review(packet) else {}


def _write_next_session_browser_qa_review_packet(
    *,
    review_contract: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": NEXT_SESSION_BROWSER_QA_REVIEW_PACKET_KEY,
        "schema_version": "next_session_browser_qa_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-08/LTG-14",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "next_session_browser_qa_review_contract": dict(review_contract),
        "next_session_browser_qa_review_rows": _as_list(review_contract.get("rows")),
        "next_session_browser_qa_evidence_status": evidence_summary.get("status"),
        "next_session_browser_qa_latest_report_path": evidence_summary.get("latest_report_path"),
        "next_session_browser_qa_latest_run_id": evidence_summary.get("latest_run_id"),
        "call_ledger": list(ledger),
        "cache_only": True,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
        "warnings": [
            "This packet is a local review receipt for ignored #next browser QA artifacts only.",
            "It does not open a browser, start servers, call providers/models/GitHub, execute trades, mutate action or operation zones, or complete production replacement.",
        ],
    }
    if _safe_persisted_browser_qa_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(NEXT_SESSION_BROWSER_QA_REVIEW_PACKET_KEY, packet)


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


def _next_session_legacy_parity_row(
    phase: str,
    status: str,
    *,
    local_ready: bool,
    parity_complete: bool,
    feature_group: str,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "local_ready": bool(local_ready),
        "parity_complete": bool(parity_complete),
        "production_blocker": not bool(parity_complete),
        "feature_group": feature_group,
        "evidence": evidence,
        "next_action": next_action,
        "required_before_production_replacement": True,
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
        "frontend_computes_trade_action": False,
        "contains_secret": False,
    }


def _next_session_legacy_parity_execution_recipe(packet: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chart = _as_dict(packet.get("chart_payload"))
    chart_contract = _as_dict(chart.get("chart_contract"))
    chart_summary = _as_dict(packet.get("chart_summary"))
    interaction_audit = _as_dict(chart.get("interaction_readiness_audit"))
    reference_rows = [row for row in _as_list(chart.get("reference_line_rows")) if isinstance(row, dict)]
    zone_rows = [row for row in _as_list(chart.get("zone_interaction_rows")) if isinstance(row, dict)]
    scenario_rows = [row for row in _as_list(chart.get("scenario_anchor_rows")) if isinstance(row, dict)]
    position_conflict = _as_dict(chart.get("position_conflict"))
    data_trust = _as_dict(chart.get("data_trust_summary"))
    exact_payload_ready = (
        chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and chart_summary.get("has_drawable_data") is True
        and chart_contract.get("renderer") == "ECharts"
    )
    interaction_contract_ready = (
        interaction_audit.get("status") == "interaction_contract_ready_parity_pending"
        and int(interaction_audit.get("blocking_count") or 0) == 0
    )
    read_only_ready = (
        chart_contract.get("cache_only") is True
        and chart_contract.get("frontend_computes_trade_action") is False
        and chart_contract.get("does_not_modify_action") is True
        and chart_contract.get("does_not_modify_operation_zones") is True
    )
    visual_feature_contract_ready = (
        bool(reference_rows)
        and bool(zone_rows)
        and bool(scenario_rows)
        and bool(position_conflict)
        and bool(_as_list(data_trust.get("facts")))
        and bool(chart.get("deepseek_status"))
    )
    rows = [
        _next_session_legacy_parity_row(
            "cache_payload_snapshot",
            "ready_local_contract",
            local_ready=exact_payload_ready,
            parity_complete=False,
            feature_group="exact ECharts cache payload",
            evidence=(
                f"status={chart.get('status')}; exact={chart.get('is_exact_next_session_packet')}; "
                f"has_drawable_data={chart_summary.get('has_drawable_data')}; renderer={chart_contract.get('renderer')}"
            ),
            next_action="Capture the same packet beside the legacy Streamlit reference before parity execution.",
        ),
        _next_session_legacy_parity_row(
            "legacy_streamlit_reference_capture",
            "pending_legacy_reference",
            local_ready=False,
            parity_complete=False,
            feature_group="legacy reference baseline",
            evidence="No current checked-in Streamlit reference screenshot or parity packet is claimed by this recipe.",
            next_action="Capture the legacy next-session visual/reference behavior explicitly before replacement promotion.",
        ),
        _next_session_legacy_parity_row(
            "chart_visual_feature_matrix",
            "pending_feature_matrix_review",
            local_ready=visual_feature_contract_ready,
            parity_complete=False,
            feature_group="latest close, scenarios, reference lines, zones, data credibility, DeepSeek status",
            evidence=(
                f"reference_rows={len(reference_rows)}; zone_rows={len(zone_rows)}; "
                f"scenario_rows={len(scenario_rows)}; data_trust_facts={len(_as_list(data_trust.get('facts')))}"
            ),
            next_action="Compare every legacy visual signal group against the React/ECharts payload without removing features.",
        ),
        _next_session_legacy_parity_row(
            "operation_zone_and_guardrail_parity",
            "pending_zone_parity",
            local_ready=bool(zone_rows) and all(row.get("frontend_mutable") is False for row in zone_rows),
            parity_complete=False,
            feature_group="operation zones and guardrails",
            evidence=f"zone_rows={len(zone_rows)}; frontend_mutable=false required.",
            next_action="Verify legacy operation-zone labels, ranges, and guardrail details are present in React/ECharts.",
        ),
        _next_session_legacy_parity_row(
            "position_conflict_and_data_trust_parity",
            "pending_context_parity",
            local_ready=bool(position_conflict) and bool(_as_list(data_trust.get("facts"))),
            parity_complete=False,
            feature_group="position conflict, freshness, data trust, provider/model status",
            evidence=f"position_conflict={bool(position_conflict)}; data_trust_facts={len(_as_list(data_trust.get('facts')))}",
            next_action="Verify conflict warnings, freshness/data trust, and DeepSeek not-called status are equally visible.",
        ),
        _next_session_legacy_parity_row(
            "hover_click_interaction_parity",
            "pending_interaction_parity",
            local_ready=interaction_contract_ready,
            parity_complete=False,
            feature_group="hover tooltip, click drilldown, source display",
            evidence=(
                f"interaction_status={interaction_audit.get('status')}; "
                f"blocking_count={interaction_audit.get('blocking_count')}"
            ),
            next_action="Run explicit hover/click comparison against legacy behavior and record reviewer evidence.",
        ),
        _next_session_legacy_parity_row(
            "browser_visual_performance_parity",
            "pending_browser_visual_performance",
            local_ready=False,
            parity_complete=False,
            feature_group="browser viewport layout and performance",
            evidence="Browser visual QA and performance trace are intentionally not executed by GET cache or this recipe.",
            next_action="Run explicit browser QA and performance trace after legacy feature matrix review.",
        ),
        _next_session_legacy_parity_row(
            "frontend_read_only_no_feature_loss_boundary",
            "ready_local_contract",
            local_ready=read_only_ready,
            parity_complete=False,
            feature_group="read-only frontend and no-feature-loss boundary",
            evidence="React/ECharts may render cache values only and must not compute action or mutate operation zones.",
            next_action="Keep replacement work render-only while closing no-feature-loss parity gaps.",
        ),
        _next_session_legacy_parity_row(
            "production_replacement_promotion",
            "blocked_until_parity_evidence",
            local_ready=False,
            parity_complete=False,
            feature_group="replacement promotion",
            evidence="Streamlit parity, browser visual QA, performance trace, reduced-motion QA, and durable evidence are pending.",
            next_action="Promote ECharts replacement only after direct evidence covers every no-feature-loss phase.",
        ),
    ]
    pending_phases = [row["phase"] for row in rows if not row["parity_complete"]]
    local_blockers = [row["phase"] for row in rows if not row["local_ready"]]
    local_recipe_ready = exact_payload_ready and interaction_contract_ready and read_only_ready and visual_feature_contract_ready
    recipe = {
        "schema_version": "next_session_legacy_parity_execution_recipe.v1",
        "status": "next_session_legacy_parity_recipe_ready_execution_pending"
        if local_recipe_ready
        else "next_session_legacy_parity_recipe_blocked",
        "scope": "local_next_session_legacy_parity_recipe_no_browser_no_provider",
        "ltg": "LTG-08/LTG-10",
        "local_recipe_ready": local_recipe_ready,
        "execution_done": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "no_feature_loss_required": True,
        "preserved_feature_groups": [
            "latest close anchor",
            "scenario paths",
            "reference and limit lines",
            "operation zones and guardrails",
            "position conflict warnings",
            "freshness and data trust",
            "DeepSeek status display",
            "hover and click drilldown",
            "read-only action boundary",
        ],
        "required_evidence": [
            "legacy Streamlit reference capture",
            "React/ECharts cache snapshot using the same packet",
            "feature-by-feature parity matrix",
            "hover/click interaction parity notes",
            "browser visual QA across default and reduced motion",
            "browser performance trace",
            "durable CI or release evidence",
            "explicit replacement promotion review",
        ],
        "allowed_next_step": "run_explicit_streamlit_reference_capture_and_browser_parity_qa",
        "not_allowed_next_steps": [
            "treat_recipe_as_streamlit_parity_completion",
            "treat_local_cache_payload_as_browser_visual_qa",
            "drop_legacy_signal_groups_to_reduce_scope",
            "compute_strategy_action_in_frontend",
            "mark_production_replacement_without_direct_evidence",
        ],
        "row_count": len(rows),
        "pending_phase_count": len(pending_phases),
        "local_blocker_count": len(local_blockers),
        "pending_phases": pending_phases,
        "local_blockers": local_blockers,
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
        "frontend_computes_trade_action": False,
        "contains_secret": False,
        "note": "This local recipe fixes the no-feature-loss acceptance path for LTG-08. It does not execute browser QA, prove Streamlit parity, or complete production replacement.",
    }
    return recipe, rows


def _next_session_durable_evidence_recipe_row(
    evidence_key: str,
    category: str,
    status: str,
    *,
    passed: bool,
    local_surface_required: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": NEXT_SESSION_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "evidence_key": evidence_key,
        "evidence_label": NEXT_SESSION_DURABLE_EVIDENCE_LABELS[evidence_key],
        "category": category,
        "status": status,
        "passed": bool(passed),
        "local_surface_required": bool(local_surface_required),
        "production_blocker": bool(production_blocker),
        "recommended_order": recommended_order,
        "evidence": evidence,
        "next_action": next_action,
        "recipe_only": True,
        "cache_only": True,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "contains_secret": False,
    }


def _next_session_durable_evidence_recipe(packet: Mapping[str, Any], now: str) -> dict[str, Any]:
    chart = _as_dict(packet.get("chart_payload"))
    chart_summary = _as_dict(packet.get("chart_summary"))
    chart_contract = _as_dict(chart.get("chart_contract"))
    interaction_audit = _as_dict(chart.get("interaction_readiness_audit"))
    activation = _as_dict(packet.get("next_session_replacement_activation_receipt"))
    parity_recipe = _as_dict(packet.get("next_session_legacy_parity_execution_recipe"))
    browser_runbook = _as_dict(packet.get("next_session_browser_qa_runbook_contract"))
    browser_evidence = _as_dict(packet.get("next_session_browser_qa_evidence_summary"))
    browser_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))

    cache_render_safe = (
        packet.get("cache_only") is not False
        and chart_contract.get("cache_only") is True
        and chart_contract.get("frontend_computes_trade_action") is False
        and chart_contract.get("does_not_modify_action") is True
        and chart_contract.get("does_not_modify_operation_zones") is True
        and chart_contract.get("external_calls_triggered") is False
        and chart_contract.get("tushare_called") is False
        and chart_contract.get("deepseek_called") is False
        and chart_contract.get("github_called") is False
    )
    exact_payload_visible = (
        chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and chart_summary.get("has_drawable_data") is True
        and chart_contract.get("renderer") == "ECharts"
    )
    interaction_visible = (
        interaction_audit.get("schema_version") == "next_session_interaction_readiness.v1"
        and interaction_audit.get("status") == "interaction_contract_ready_parity_pending"
        and int(interaction_audit.get("blocking_count") or 0) == 0
    )
    parity_recipe_visible = (
        parity_recipe.get("schema_version") == "next_session_legacy_parity_execution_recipe.v1"
        and parity_recipe.get("local_recipe_ready") is True
    )
    browser_runbook_visible = (
        browser_runbook.get("schema_version") == "next_session_browser_qa_runbook.v1"
        and browser_runbook.get("local_runbook_ready") is True
    )
    local_browser_review_visible = (
        browser_review.get("schema_version") == "next_session_browser_qa_review.v1"
        and browser_review.get("scope") == "button_gated_local_next_session_browser_qa_review_no_browser_execution"
    )
    local_browser_visual_perf_reviewed = (
        browser_evidence.get("next_visual_qa_evidence_passed") is True
        and browser_evidence.get("next_browser_performance_evidence_passed") is True
        and browser_review.get("local_browser_qa_review_ready") is True
    )
    streamlit_parity_complete = activation.get("streamlit_parity_complete") is True
    production_replacement_complete = activation.get("production_replacement_complete") is True
    durable_ci_evidence_complete = activation.get("durable_ci_evidence_complete") is True
    no_provider_trade_action_secret_boundary = (
        activation.get("external_calls_triggered") is False
        and activation.get("tushare_called") is False
        and activation.get("deepseek_called") is False
        and activation.get("github_called") is False
        and activation.get("does_not_execute_trades") is True
        and activation.get("does_not_modify_strategy_action") is True
        and activation.get("does_not_modify_operation_zones") is True
    )

    rows = [
        _next_session_durable_evidence_recipe_row(
            "cache_render_boundary_visible",
            "local_surface",
            "passed_cache_render_boundary" if cache_render_safe else "blocked_cache_render_boundary",
            passed=cache_render_safe,
            local_surface_required=True,
            production_blocker=False,
            evidence=(
                f"cache_only={chart_contract.get('cache_only')}; "
                f"frontend_computes_trade_action={chart_contract.get('frontend_computes_trade_action')}"
            ),
            next_action="Keep GET cache and React render read-only, provider-silent, and action-silent.",
            recommended_order=1,
        ),
        _next_session_durable_evidence_recipe_row(
            "exact_echarts_payload_visible",
            "local_surface",
            "passed_exact_payload" if exact_payload_visible else "blocked_exact_payload",
            passed=exact_payload_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=(
                f"chart_status={chart.get('status')}; exact={chart.get('is_exact_next_session_packet')}; "
                f"renderer={chart_contract.get('renderer')}"
            ),
            next_action="Keep exact ECharts payload and latest-close/reference/zone context visible before parity execution.",
            recommended_order=2,
        ),
        _next_session_durable_evidence_recipe_row(
            "interaction_contract_visible",
            "local_surface",
            "passed_interaction_contract" if interaction_visible else "blocked_interaction_contract",
            passed=interaction_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={interaction_audit.get('status')}; blocking_count={interaction_audit.get('blocking_count')}",
            next_action="Keep hover/click/source/guardrail rows visible while parity remains pending.",
            recommended_order=3,
        ),
        _next_session_durable_evidence_recipe_row(
            "legacy_parity_recipe_visible",
            "local_surface",
            "passed_legacy_parity_recipe" if parity_recipe_visible else "blocked_legacy_parity_recipe",
            passed=parity_recipe_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={parity_recipe.get('status')}; pending={parity_recipe.get('pending_phase_count')}",
            next_action="Use the parity recipe as a no-feature-loss checklist, not as completed Streamlit parity.",
            recommended_order=4,
        ),
        _next_session_durable_evidence_recipe_row(
            "browser_qa_runbook_visible",
            "local_surface",
            "passed_browser_qa_runbook" if browser_runbook_visible else "blocked_browser_qa_runbook",
            passed=browser_runbook_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={browser_runbook.get('status')}; route={browser_runbook.get('next_route')}",
            next_action="Keep browser QA execution explicit and outside GET/render paths.",
            recommended_order=5,
        ),
        _next_session_durable_evidence_recipe_row(
            "local_browser_qa_review_visible",
            "local_surface",
            "passed_local_review_surface" if local_browser_review_visible else "blocked_local_review_surface",
            passed=local_browser_review_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=(
                f"status={browser_review.get('status')}; "
                f"local_review_ready={browser_review.get('local_browser_qa_review_ready')}"
            ),
            next_action="Treat local QA review as a local artifact review only; durable promotion still needs direct evidence.",
            recommended_order=6,
        ),
        _next_session_durable_evidence_recipe_row(
            "streamlit_reference_capture_required",
            "durable_evidence",
            "completed" if streamlit_parity_complete else "pending_streamlit_reference_capture",
            passed=streamlit_parity_complete,
            local_surface_required=False,
            production_blocker=not streamlit_parity_complete,
            evidence=f"streamlit_parity_complete={streamlit_parity_complete}",
            next_action="Capture Streamlit reference behavior for the same packet before claiming replacement parity.",
            recommended_order=7,
        ),
        _next_session_durable_evidence_recipe_row(
            "feature_by_feature_parity_required",
            "durable_evidence",
            "completed" if streamlit_parity_complete else "pending_feature_parity_matrix",
            passed=streamlit_parity_complete,
            local_surface_required=False,
            production_blocker=not streamlit_parity_complete,
            evidence=f"preserved_feature_groups={len(_as_list(parity_recipe.get('preserved_feature_groups')))}",
            next_action="Review every legacy signal group against React/ECharts without dropping behavior to reduce scope.",
            recommended_order=8,
        ),
        _next_session_durable_evidence_recipe_row(
            "hover_click_parity_required",
            "durable_evidence",
            "completed" if streamlit_parity_complete else "pending_hover_click_parity",
            passed=streamlit_parity_complete,
            local_surface_required=False,
            production_blocker=not streamlit_parity_complete,
            evidence=f"interaction_visible={interaction_visible}; streamlit_parity_complete={streamlit_parity_complete}",
            next_action="Record hover/click parity notes against legacy behavior before promotion.",
            recommended_order=9,
        ),
        _next_session_durable_evidence_recipe_row(
            "durable_browser_visual_performance_evidence_required",
            "durable_evidence",
            "completed" if False else "pending_durable_browser_visual_performance",
            passed=False,
            local_surface_required=False,
            production_blocker=True,
            evidence=(
                f"local_visual_perf_reviewed={local_browser_visual_perf_reviewed}; "
                f"visual={browser_evidence.get('next_visual_qa_evidence_passed')}; "
                f"performance={browser_evidence.get('next_browser_performance_evidence_passed')}"
            ),
            next_action="Promote ignored local reports only after durable reviewer/CI/release evidence is attached.",
            recommended_order=10,
        ),
        _next_session_durable_evidence_recipe_row(
            "durable_ci_release_evidence_required",
            "durable_evidence",
            "completed" if durable_ci_evidence_complete else "pending_durable_ci_release_evidence",
            passed=durable_ci_evidence_complete,
            local_surface_required=False,
            production_blocker=not durable_ci_evidence_complete,
            evidence=f"durable_ci_evidence_complete={durable_ci_evidence_complete}",
            next_action="Keep local artifacts separate from durable CI/release evidence.",
            recommended_order=11,
        ),
        _next_session_durable_evidence_recipe_row(
            "production_replacement_review_required",
            "durable_evidence",
            "completed" if production_replacement_complete else "pending_production_replacement_review",
            passed=production_replacement_complete,
            local_surface_required=False,
            production_blocker=not production_replacement_complete,
            evidence=f"production_replacement_complete={production_replacement_complete}",
            next_action="Promote ECharts replacement only after parity, visual QA, performance trace, durable evidence, and review pass.",
            recommended_order=12,
        ),
        _next_session_durable_evidence_recipe_row(
            "no_provider_trade_action_secret_boundary",
            "safety",
            "passed_no_provider_trade_action_secret" if no_provider_trade_action_secret_boundary else "blocked_safety_boundary",
            passed=no_provider_trade_action_secret_boundary,
            local_surface_required=True,
            production_blocker=not no_provider_trade_action_secret_boundary,
            evidence="Recipe calls no provider/model/probe, executes no trades, mutates no strategy action or operation zones, and exposes no secret.",
            next_action="Preserve provider/model/trade/action/secret boundaries while durable evidence improves.",
            recommended_order=13,
        ),
    ]
    local_blockers = [row["evidence_key"] for row in rows if row["local_surface_required"] and not row["passed"]]
    durable_blockers = [row["evidence_key"] for row in rows if row["production_blocker"] and not row["passed"]]
    local_ready = not local_blockers
    contract = {
        "schema_version": NEXT_SESSION_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "next_session_durable_evidence_recipe_ready_production_pending"
            if local_ready
            else "next_session_durable_evidence_recipe_blocked_local_surface"
        ),
        "scope": "local_next_session_durable_evidence_recipe_no_browser_no_provider",
        "ltg": "LTG-08/LTG-10/LTG-14",
        "local_recipe_ready": local_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "production_replacement_complete": False,
        "streamlit_parity_complete": False,
        "streamlit_reference_captured": False,
        "feature_by_feature_parity_complete": False,
        "hover_click_parity_complete": False,
        "browser_visual_performance_reviewed": False,
        "local_browser_visual_performance_reviewed": local_browser_visual_perf_reviewed,
        "durable_ci_evidence_complete": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_execution_implemented": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "page_render_starts_browser": False,
        "page_render_starts_provider": False,
        "page_render_starts_model": False,
        "evidence_keys": list(NEXT_SESSION_DURABLE_EVIDENCE_KEYS),
        "missing_durable_evidence": durable_blockers,
        "required_evidence": [
            "same-packet Streamlit reference capture",
            "feature-by-feature legacy parity matrix",
            "hover/click parity notes",
            "durable browser visual/performance evidence for #next",
            "durable CI or release evidence",
            "explicit production replacement promotion review",
        ],
        "not_allowed_next_steps": [
            "treat durable recipe as ECharts production replacement",
            "treat local browser artifact review as durable evidence",
            "treat interaction readiness as Streamlit parity",
            "drop legacy signal groups to reduce scope",
            "call Tushare or DeepSeek from GET cache or React render",
            "open browser or start servers from durable recipe",
            "compute strategy action in frontend",
            "mutate price, position, strategy action, or operation zones",
            "store raw token/key in packet, cache, ledger, log, or frontend",
        ],
        "allowed_next_step": "run_same_packet_streamlit_parity_then_browser_visual_performance_then_durable_promotion_review",
        "row_count": len(rows),
        "evidence_key_count": len(NEXT_SESSION_DURABLE_EVIDENCE_KEYS),
        "local_blocker_count": len(local_blockers),
        "durable_evidence_blocker_count": len(durable_blockers),
        "production_blocker_count": len(durable_blockers),
        "local_blockers": local_blockers,
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "note": "This recipe fixes the durable evidence checklist for LTG-08. It does not open a browser, start servers, call providers/models/GitHub, execute trades, mutate action or operation zones, prove Streamlit parity, or complete ECharts production replacement.",
    }
    contract["call_ledger"] = [
        {
            "api": "local_next_session_durable_evidence_recipe",
            "request_params_safe": {
                "status": contract["status"],
                "row_count": len(rows),
                "production_blocker_count": len(durable_blockers),
                "production_replacement_complete": False,
            },
            "row_count": len(rows),
            "data_date": _next_session_data_date(dict(packet)),
            "local_fetched_at": now,
            "call_status": contract["status"],
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]
    return contract


def _next_session_production_stage_scope_row(
    stage_key: str,
    *,
    local_contract_ready: bool,
    direct_evidence_complete: bool,
    current_status: str,
    evidence: str,
    missing_evidence: list[str],
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": NEXT_SESSION_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION,
        "stage_key": stage_key,
        "stage_label": NEXT_SESSION_PRODUCTION_STAGE_LABELS[stage_key],
        "scope": "next_session_production_replacement_stage_scope_manifest",
        "current_status": current_status,
        "target_status": "browser_parity_or_release_evidence_required",
        "required_before_production_replacement": True,
        "recommended_order": recommended_order,
        "local_contract_ready": bool(local_contract_ready),
        "direct_evidence_complete": bool(direct_evidence_complete),
        "local_only_direct_evidence": bool(direct_evidence_complete),
        "durable_evidence_complete": False,
        "production_blocker": not bool(direct_evidence_complete),
        "evidence": evidence,
        "missing_evidence": missing_evidence,
        "streamlit_parity_complete": False,
        "browser_visual_qa_done": stage_key == "browser_visual_qa" and direct_evidence_complete,
        "browser_performance_trace_done": stage_key == "browser_performance_trace" and direct_evidence_complete,
        "reduced_motion_accessibility_qa_done": (
            stage_key == "reduced_motion_accessibility_qa" and direct_evidence_complete
        ),
        "durable_ci_evidence_complete": False,
        "production_replacement_complete": False,
        "browser_opened_by_contract": False,
        "artifacts_written_by_contract": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "contains_secret": False,
    }


def _next_session_production_stage_scope_manifest(packet: Mapping[str, Any], now: str) -> dict[str, Any]:
    chart = _as_dict(packet.get("chart_payload"))
    chart_summary = _as_dict(packet.get("chart_summary"))
    chart_contract = _as_dict(chart.get("chart_contract"))
    interaction_audit = _as_dict(chart.get("interaction_readiness_audit"))
    browser_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    browser_evidence = _as_dict(packet.get("next_session_browser_qa_evidence_summary"))
    activation = _as_dict(packet.get("next_session_replacement_activation_receipt"))

    exact_payload_contract_ready = (
        chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and chart_summary.get("has_drawable_data") is True
        and chart_contract.get("schema_version") == "next_session_echarts_payload.v1"
        and chart_contract.get("renderer") == "ECharts"
    )
    interaction_contract_ready = (
        interaction_audit.get("schema_version") == "next_session_interaction_readiness.v1"
        and interaction_audit.get("status") == "interaction_contract_ready_parity_pending"
        and int(interaction_audit.get("blocking_count") or 0) == 0
    )
    local_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    browser_visual_done = (
        local_review_ready
        and browser_evidence.get("next_visual_qa_evidence_passed") is True
        and browser_review.get("next_visual_qa_evidence_passed") is True
    )
    browser_performance_done = (
        local_review_ready
        and browser_evidence.get("next_browser_performance_evidence_passed") is True
        and browser_review.get("next_browser_performance_evidence_passed") is True
    )
    reduced_motion_done = (
        local_review_ready
        and browser_review.get("default_motion_passed") is True
        and browser_review.get("reduced_motion_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
    )

    rows = [
        _next_session_production_stage_scope_row(
            "exact_cache_payload_contract",
            local_contract_ready=exact_payload_contract_ready,
            direct_evidence_complete=False,
            current_status="local_contract_ready" if exact_payload_contract_ready else "pending_exact_cache_payload",
            evidence=(
                f"chart_status={chart.get('status')}; exact={chart.get('is_exact_next_session_packet')}; "
                f"renderer={chart_contract.get('renderer')}"
            ),
            missing_evidence=["same-packet Streamlit reference capture", "browser parity review"],
            recommended_order=1,
        ),
        _next_session_production_stage_scope_row(
            "interaction_hover_click_contract",
            local_contract_ready=interaction_contract_ready,
            direct_evidence_complete=False,
            current_status="local_contract_ready" if interaction_contract_ready else "pending_interaction_contract",
            evidence=(
                f"status={interaction_audit.get('status')}; "
                f"blocking_count={interaction_audit.get('blocking_count')}"
            ),
            missing_evidence=["hover/click parity notes against Streamlit", "browser interaction QA review"],
            recommended_order=2,
        ),
        _next_session_production_stage_scope_row(
            "streamlit_parity_review",
            local_contract_ready=False,
            direct_evidence_complete=False,
            current_status="pending_same_packet_streamlit_parity",
            evidence=f"streamlit_parity_complete={activation.get('streamlit_parity_complete') is True}",
            missing_evidence=["explicit same-packet Streamlit reference capture", "feature-by-feature parity matrix"],
            recommended_order=3,
        ),
        _next_session_production_stage_scope_row(
            "browser_visual_qa",
            local_contract_ready=browser_evidence.get("local_browser_qa_evidence_found") is True,
            direct_evidence_complete=browser_visual_done,
            current_status=(
                "direct_evidence_ready_local_artifact" if browser_visual_done else "pending_browser_visual_qa_review"
            ),
            evidence=(
                f"local_review_ready={local_review_ready}; "
                f"visual={browser_evidence.get('next_visual_qa_evidence_passed')}"
            ),
            missing_evidence=[] if browser_visual_done else ["button-gated local browser QA review for #next visual rows"],
            recommended_order=4,
        ),
        _next_session_production_stage_scope_row(
            "browser_performance_trace",
            local_contract_ready=browser_evidence.get("local_browser_qa_evidence_found") is True,
            direct_evidence_complete=browser_performance_done,
            current_status=(
                "direct_evidence_ready_local_artifact"
                if browser_performance_done
                else "pending_browser_performance_trace_review"
            ),
            evidence=(
                f"local_review_ready={local_review_ready}; "
                f"performance={browser_evidence.get('next_browser_performance_evidence_passed')}"
            ),
            missing_evidence=[] if browser_performance_done else ["button-gated local browser QA review for #next performance rows"],
            recommended_order=5,
        ),
        _next_session_production_stage_scope_row(
            "reduced_motion_accessibility_qa",
            local_contract_ready=browser_evidence.get("motion_viewport_coverage_complete") is True,
            direct_evidence_complete=reduced_motion_done,
            current_status=(
                "direct_evidence_ready_local_artifact"
                if reduced_motion_done
                else "pending_reduced_motion_accessibility_review"
            ),
            evidence=(
                f"default_motion={browser_review.get('default_motion_passed')}; "
                f"reduced_motion={browser_review.get('reduced_motion_passed')}; "
                f"viewport_coverage={browser_review.get('motion_viewport_coverage_complete')}"
            ),
            missing_evidence=[] if reduced_motion_done else ["default and reduced-motion #next viewport coverage review"],
            recommended_order=6,
        ),
        _next_session_production_stage_scope_row(
            "durable_ci_release_evidence",
            local_contract_ready=False,
            direct_evidence_complete=False,
            current_status="pending_durable_ci_release_evidence",
            evidence=f"durable_ci_evidence_complete={activation.get('durable_ci_evidence_complete') is True}",
            missing_evidence=["durable CI or release evidence for next-session ECharts route"],
            recommended_order=7,
        ),
        _next_session_production_stage_scope_row(
            "production_replacement_promotion",
            local_contract_ready=False,
            direct_evidence_complete=False,
            current_status="pending_production_replacement_promotion",
            evidence=f"production_replacement_complete={activation.get('production_replacement_complete') is True}",
            missing_evidence=["explicit production replacement promotion review"],
            recommended_order=8,
        ),
    ]
    direct_stage_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is True]
    pending_stage_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is not True]
    local_contract_stage_keys = [row["stage_key"] for row in rows if row["local_contract_ready"] is True]
    manifest = {
        "schema_version": NEXT_SESSION_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION,
        "status": "next_session_production_stage_scope_manifest_ready_production_pending",
        "scope": "next_session_production_replacement_stage_scope_manifest",
        "ltg": "LTG-08/LTG-13",
        "local_manifest_ready": True,
        "stage_count": len(rows),
        "direct_evidence_stage_count": len(direct_stage_keys),
        "pending_stage_count": len(pending_stage_keys),
        "production_blocker_count": len(pending_stage_keys),
        "stage_keys": list(NEXT_SESSION_PRODUCTION_STAGE_KEYS),
        "direct_evidence_stage_keys": direct_stage_keys,
        "pending_stage_keys": pending_stage_keys,
        "local_contract_stage_keys": local_contract_stage_keys,
        "browser_visual_qa_done": browser_visual_done,
        "browser_performance_trace_done": browser_performance_done,
        "reduced_motion_accessibility_qa_done": reduced_motion_done,
        "local_browser_qa_review_ready": local_review_ready,
        "streamlit_parity_complete": False,
        "durable_ci_evidence_complete": False,
        "production_replacement_complete": False,
        "durable_promotion_ready": False,
        "can_close_ltg08": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "allowed_next_step": "run_same_packet_streamlit_parity_then_durable_browser_and_release_promotion_review",
        "not_allowed_next_steps": [
            "treat local browser QA as production ECharts replacement",
            "treat local stage scope as durable CI or release evidence",
            "call Tushare or DeepSeek from GET cache or React render",
            "compute strategy action in frontend",
            "mutate price, position, strategy action, or operation zones",
        ],
        "rows": rows,
        "note": "This manifest makes LTG-08 stage evidence visible from GET cache and React. It does not run browser QA, call providers/models/GitHub, execute trades, prove Streamlit parity, or complete production replacement.",
    }
    manifest["call_ledger"] = [
        {
            "api": "local_next_session_production_stage_scope_manifest",
            "request_params_safe": {
                "stage_count": len(rows),
                "direct_evidence_stage_count": len(direct_stage_keys),
                "pending_stage_count": len(pending_stage_keys),
                "production_replacement_complete": False,
            },
            "row_count": len(rows),
            "data_date": _next_session_data_date(dict(packet)),
            "local_fetched_at": now,
            "call_status": manifest["status"],
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]
    return manifest


def read_next_session_cache() -> dict[str, Any]:
    packet = dict(packet_service.build_next_session_cache())
    activation_receipt, activation_rows = _next_session_replacement_activation_receipt(packet)
    legacy_parity_recipe, legacy_parity_rows = _next_session_legacy_parity_execution_recipe(packet)
    (
        browser_qa_runbook,
        browser_qa_runbook_rows,
        browser_qa_matrix_rows,
    ) = _next_session_browser_qa_runbook_contract()
    browser_qa_evidence, browser_qa_evidence_rows = _next_session_browser_qa_evidence_summary()
    persisted_browser_qa_review_packet = _read_next_session_browser_qa_review_packet()
    persisted_browser_qa_review = _as_dict(
        persisted_browser_qa_review_packet.get("next_session_browser_qa_review_contract")
    )
    existing_browser_qa_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    if persisted_browser_qa_review.get("explicit_review_task_done") is True:
        browser_qa_review = persisted_browser_qa_review
    elif existing_browser_qa_review.get("explicit_review_task_done") is True:
        browser_qa_review = existing_browser_qa_review
    else:
        browser_qa_review = _next_session_browser_qa_review_contract(browser_qa_evidence, browser_qa_evidence_rows)
    packet["next_session_replacement_activation_receipt"] = activation_receipt
    packet["next_session_replacement_activation_rows"] = activation_rows
    packet["next_session_legacy_parity_execution_recipe"] = legacy_parity_recipe
    packet["next_session_legacy_parity_execution_rows"] = legacy_parity_rows
    packet["next_session_legacy_parity_recipe_ready"] = legacy_parity_recipe["local_recipe_ready"]
    packet["next_session_legacy_parity_pending_phase_count"] = legacy_parity_recipe["pending_phase_count"]
    packet["next_session_browser_qa_runbook_contract"] = browser_qa_runbook
    packet["next_session_browser_qa_runbook_rows"] = browser_qa_runbook_rows
    packet["next_session_browser_qa_matrix_rows"] = browser_qa_matrix_rows
    packet["next_session_browser_qa_evidence_summary"] = browser_qa_evidence
    packet["next_session_browser_qa_evidence_rows"] = browser_qa_evidence_rows
    packet["next_session_browser_qa_review_contract"] = browser_qa_review
    packet["next_session_browser_qa_review_rows"] = _as_list(browser_qa_review.get("rows"))
    durable_evidence_recipe = _next_session_durable_evidence_recipe(packet, _now_iso())
    packet["next_session_durable_evidence_recipe"] = durable_evidence_recipe
    packet["next_session_durable_evidence_rows"] = durable_evidence_recipe["rows"]
    production_stage_scope = _next_session_production_stage_scope_manifest(packet, _now_iso())
    packet["next_session_production_stage_scope_manifest"] = production_stage_scope
    packet["next_session_production_stage_scope_rows"] = production_stage_scope["rows"]
    packet["next_session_activation_receipt_ready"] = activation_receipt["local_activation_receipt_ready"]
    packet["next_session_activation_production_blocker_count"] = activation_receipt["production_blocker_count"]
    packet["next_session_activation_missing_evidence_count"] = activation_receipt["missing_evidence_count"]
    packet["next_session_browser_qa_runbook_ready"] = browser_qa_runbook["local_runbook_ready"]
    packet["next_session_browser_qa_evidence_ready"] = browser_qa_evidence["next_browser_qa_evidence_ready"]
    packet["next_session_browser_qa_review_ready"] = browser_qa_review["local_browser_qa_review_ready"]
    packet["next_session_browser_qa_review_blocking_count"] = browser_qa_review["blocking_review_count"]
    packet["next_session_durable_evidence_recipe_ready"] = durable_evidence_recipe["local_recipe_ready"]
    packet["next_session_durable_evidence_blocker_count"] = durable_evidence_recipe["durable_evidence_blocker_count"]
    packet["next_session_production_stage_scope_ready"] = production_stage_scope["local_manifest_ready"]
    packet["next_session_production_stage_scope_direct_evidence_count"] = production_stage_scope[
        "direct_evidence_stage_count"
    ]
    packet["next_session_production_stage_scope_pending_count"] = production_stage_scope["pending_stage_count"]
    packet["next_session_production_stage_scope_blocker_count"] = production_stage_scope["production_blocker_count"]
    counts = _as_dict(packet.get("counts"))
    counts.update(
        {
            "next_session_production_stage_scope_count": production_stage_scope["stage_count"],
            "next_session_production_stage_scope_direct_evidence_count": production_stage_scope[
                "direct_evidence_stage_count"
            ],
            "next_session_production_stage_scope_pending_count": production_stage_scope["pending_stage_count"],
            "next_session_production_stage_scope_blocker_count": production_stage_scope["production_blocker_count"],
        }
    )
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy.update(
        {
            "next_session_production_stage_scope_manifest_is_local": True,
            "next_session_production_stage_scope_is_not_browser_execution": True,
            "next_session_production_stage_scope_is_not_production_completion": True,
            "next_session_production_stage_scope_calls_no_provider_model_or_github": True,
        }
    )
    packet["policy"] = policy
    existing_ledger = [row for row in _as_list(packet.get("call_ledger")) if isinstance(row, dict)]
    if not existing_ledger:
        existing_ledger = _next_session_cache_call_ledger(packet, _now_iso())
    review_ledger = [
        row for row in _as_list(persisted_browser_qa_review_packet.get("call_ledger")) if isinstance(row, dict)
    ]
    if review_ledger:
        existing_ledger.extend(review_ledger)
    packet["call_ledger"] = (
        existing_ledger + durable_evidence_recipe["call_ledger"] + production_stage_scope["call_ledger"]
    )
    warnings = [str(item) for item in _as_list(packet.get("warnings"))]
    for warning in [
        "GET /api/next-session/cache 只读取本地次日图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
        " next_session_replacement_activation_receipt 只是替代验收路径，不运行浏览器、不证明生产替代完成。",
        "next_session_durable_evidence_recipe 只固定 ECharts 生产替代前的 durable evidence 清单；不会打开浏览器、调用 provider/model、执行交易或证明生产替代完成。",
        "next_session_production_stage_scope_manifest 只把本地阶段证据和剩余阻断暴露到 cache/UI；不会运行浏览器、不会调用 provider/model/GitHub、不会证明生产替代完成。",
    ]:
        if warning not in warnings:
            warnings.append(warning)
    packet["warnings"] = warnings
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
    _write_next_session_browser_qa_review_packet(
        review_contract=review_contract,
        evidence_summary=evidence_summary,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
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
