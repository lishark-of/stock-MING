from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import motion_evidence_service, packet_service
from .request_local_memo import memoize_request_local_read
from .task_service import create_task_record, update_task_status

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
MOTION_QA_ARTIFACT_ROOT = PROJECT_ROOT / ".stock_ming_3" / "motion_qa"
MOTION_BROWSER_QA_RUNNER_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runner.mjs"
NEXT_SESSION_ROUTE_SOURCE_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "NextSessionMap.tsx"
LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION = "command_center_3_local_push_gate_run_receipt.v1"
LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "local_push_gate_run_receipt.json"
NEXT_SESSION_BROWSER_QA_REVIEW_PACKET_KEY = "command_center_next_session_browser_qa_review_packet"
NEXT_SESSION_STREAMLIT_PARITY_REVIEW_PACKET_KEY = "command_center_next_session_streamlit_parity_review_packet"
NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY = (
    "command_center_next_session_production_promotion_review_packet"
)
CANDIDATE_RADAR_PACKET_KEY = "command_center_3_candidate_radar_cache"
NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION = "next_session_production_promotion_review.v1"
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
    "streamlit_parity_review": "legacy signal/capability parity review",
    "browser_visual_qa": "browser visual QA across viewports",
    "browser_performance_trace": "browser performance trace",
    "reduced_motion_accessibility_qa": "reduced-motion and accessibility QA",
    "durable_ci_release_evidence": "durable CI or release evidence",
    "production_replacement_promotion": "production replacement promotion review",
}
NEXT_SESSION_RELEASE_GATE_REQUIRED_CHECKS = {
    "python_unittest",
    "desktop_build",
    "command_center_3_smoke",
    "next_session_map_contract",
    "diff_whitespace_check",
    "high_risk_secret_scan",
    "secret_keyword_review_contract",
    "generated_artifact_scan",
    "clean_worktree_check",
}


def _sync_packet_service_sqlite_path() -> None:
    if Path(packet_service.SQLITE_META_PATH) != Path(SQLITE_META_PATH):
        packet_service.SQLITE_META_PATH = SQLITE_META_PATH


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


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _git_dir_path() -> Path:
    dot_git = PROJECT_ROOT / ".git"
    if dot_git.is_file():
        text = _read_local_text(dot_git).strip()
        if text.startswith("gitdir:"):
            raw_path = text.split(":", 1)[1].strip()
            path = Path(raw_path)
            return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    return dot_git


def _current_git_head_summary() -> dict[str, Any]:
    git_dir = _git_dir_path()
    head_file = git_dir / "HEAD"
    head_text = _read_local_text(head_file).strip()
    if not head_text:
        return {"read_status": "git_head_missing", "branch": "", "head_full": "", "head": ""}
    if head_text.startswith("ref:"):
        ref_name = head_text.split(":", 1)[1].strip()
        ref_text = _read_local_text(git_dir / ref_name).strip()
        head_full = ref_text if ref_text else ""
        return {
            "read_status": "git_head_ref_present" if head_full else "git_head_ref_missing",
            "branch": ref_name.removeprefix("refs/heads/"),
            "head_full": head_full,
            "head": head_full[:7],
            "ref": ref_name,
        }
    return {"read_status": "git_head_detached", "branch": "HEAD", "head_full": head_text, "head": head_text[:7], "ref": ""}


def _read_next_session_local_release_gate_receipt() -> dict[str, Any]:
    current_head = _current_git_head_summary()
    base = {
        "schema_version": LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
        "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
        "receipt_path": _relative_path(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH),
        "current_head": current_head.get("head") or "",
        "current_head_full": current_head.get("head_full") or "",
        "current_branch": current_head.get("branch") or "",
        "head_matches_current": False,
        "fresh_local_gate_run_observed": False,
        "required_local_gate_checks_present": False,
        "required_check_count": len(NEXT_SESSION_RELEASE_GATE_REQUIRED_CHECKS),
        "observed_check_count": 0,
        "missing_required_checks": sorted(NEXT_SESSION_RELEASE_GATE_REQUIRED_CHECKS),
        "did_not_push": True,
        "git_add_dot_used": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "local_gate_pass_is_not_ci_status": True,
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
    }
    if not LOCAL_PUSH_GATE_RUN_RECEIPT_PATH.exists():
        return {**base, "status": "local_push_gate_run_receipt_missing", "read_status": "receipt_missing"}
    try:
        raw = json.loads(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {**base, "status": "local_push_gate_run_receipt_unreadable", "read_status": "receipt_read_failed"}
    receipt = _as_dict(raw)
    checks = {str(item) for item in _as_list(receipt.get("checks"))}
    missing_checks = sorted(NEXT_SESSION_RELEASE_GATE_REQUIRED_CHECKS.difference(checks))
    receipt_head_full = str(receipt.get("head_full") or "")
    receipt_head = str(receipt.get("head") or "")
    current_head_full = str(current_head.get("head_full") or "")
    current_head_short = str(current_head.get("head") or "")
    head_matches_current = bool(
        current_head_full
        and (
            receipt_head_full == current_head_full
            or (receipt_head and current_head_short and receipt_head == current_head_short)
        )
    )
    boundary_ok = (
        receipt.get("did_not_push") is True
        and receipt.get("git_add_dot_used") is False
        and receipt.get("external_calls_triggered") is False
        and receipt.get("tushare_called") is False
        and receipt.get("deepseek_called") is False
        and receipt.get("github_api_called") is False
        and receipt.get("does_not_execute_trades") is True
        and receipt.get("does_not_modify_strategy_action") is True
        and receipt.get("contains_secret") is False
    )
    schema_ok = receipt.get("schema_version") == LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION
    status_ok = receipt.get("status") == "local_push_gate_passed_current_head"
    checks_ok = not missing_checks
    fresh = bool(schema_ok and status_ok and head_matches_current and boundary_ok and checks_ok)
    return {
        **base,
        "schema_version": str(receipt.get("schema_version") or LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION),
        "status": receipt.get("status") if schema_ok else "local_push_gate_run_receipt_schema_mismatch",
        "read_status": "receipt_present",
        "generated_at_utc": str(receipt.get("generated_at_utc") or ""),
        "branch": str(receipt.get("branch") or ""),
        "head": receipt_head,
        "head_full": receipt_head_full,
        "head_matches_current": head_matches_current,
        "boundary_flags_valid": boundary_ok,
        "fresh_local_gate_run_observed": fresh,
        "required_local_gate_checks_present": checks_ok,
        "observed_check_count": len(checks),
        "missing_required_checks": missing_checks,
        "did_not_push": receipt.get("did_not_push") is True,
        "git_add_dot_used": receipt.get("git_add_dot_used") is True,
        "github_api_called": receipt.get("github_api_called") is True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
    }


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


def _source_task_readback_text(value: Any, *, source_task_tushare_called: bool, limit: int = 360) -> str:
    text = _safe_text(value, limit=limit)
    if not source_task_tushare_called or not text or "本次 GET cache 未外联" in text:
        return text
    text = text.replace("可读结论：Tushare-first", "可读结论：源任务 Tushare-first")
    text = text.replace("Tushare-first 账本", "源任务 Tushare-first 账本", 1) if "源任务" not in text else text
    if "个接口；" in text:
        text = text.replace("个接口；", "个接口；本次 GET cache 未外联；", 1)
    elif "个接口。" in text:
        text = text.replace("个接口。", "个接口；本次 GET cache 未外联。", 1)
    else:
        text = f"{text}；本次 GET cache 未外联。"
    return _safe_text(text, limit=limit)


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
        {"name": "desktop", "width": 1440, "height": 900},
        {"name": "laptop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 834, "height": 1112},
        {"name": "mobile", "width": 390, "height": 844},
    ]
    runner_source = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    route_source = _read_local_text(NEXT_SESSION_ROUTE_SOURCE_PATH)
    runner_available = (
        MOTION_BROWSER_QA_RUNNER_PATH.exists()
        and "#next-session-chart" in runner_source
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
            evidence="Shared motion runner covers #next-session-chart and NextSessionMap exposes the replacement activation receipt.",
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
            "route": "#next-session-chart",
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
        "next_route": "#next-session-chart",
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
        "note": "This runbook prepares targeted #next-session-chart browser QA. It is not browser execution, legacy signal/capability parity, performance promotion, or production replacement.",
    }
    return contract, rows, matrix_rows


def _read_next_session_browser_qa_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _browser_qa_report_sort_key(path: Path, report: Mapping[str, Any]) -> tuple[float, str]:
    generated_at = str(report.get("generated_at") or "").strip()
    if generated_at:
        try:
            parsed = _dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            return parsed.timestamp(), str(path)
        except Exception:
            pass
    try:
        return path.stat().st_mtime, str(path)
    except Exception:
        return 0.0, str(path)


def _next_motion_transition_us(report: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[int | None, int | None]:
    observed = row.get("route_transition_observed_us")
    budget = row.get("route_transition_budget_us") or _as_dict(report.get("performance_budgets")).get("route_transition_observed_us")
    if type(observed) is int and type(budget) is int:
        return observed, budget
    try:
        legacy_observed = row.get("route_transition_observed_ms")
        legacy_budget = row.get("route_transition_budget_ms") or _as_dict(report.get("performance_budgets")).get("route_transition_observed_ms")
        return int(round(float(legacy_observed) * 1000)), int(round(float(legacy_budget) * 1000))
    except Exception:
        return None, None


def _next_layout_shift_ppm(row: Mapping[str, Any]) -> int | None:
    value = row.get("largest_motion_layout_shift_ppm")
    if type(value) is int:
        return value
    try:
        return int(round(float(row.get("largest_motion_layout_shift")) * 1_000_000))
    except Exception:
        return None


def _next_session_report_rows_passed(report: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        transition_observed, transition_budget = _next_motion_transition_us(report, row)
        transition_within_budget = transition_observed is not None and transition_budget is not None and transition_observed <= transition_budget
        if (
            str(row.get("status") or "") != "passed"
            or row.get("visual_qa_complete") is not True
            or row.get("performance_trace_complete") is not True
            or int(row.get("long_task_over_50ms_count") or 0) != 0
            or int(row.get("clipped_count") or 0) != 0
            or not transition_within_budget
        ):
            return False
    return True


def _next_session_browser_qa_evidence_row(report: Mapping[str, Any], row: Mapping[str, Any], report_path: Path) -> dict[str, Any]:
    transition_observed, transition_budget = _next_motion_transition_us(report, row)
    transition_within_budget = transition_observed is not None and transition_budget is not None and transition_observed <= transition_budget
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
        "route_transition_observed_us": transition_observed,
        "route_transition_budget_us": transition_budget,
        "long_task_over_50ms_count": long_task_count,
        "largest_motion_layout_shift_ppm": _next_layout_shift_ppm(row),
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
    report_paths = sorted(MOTION_QA_ARTIFACT_ROOT.glob("*/motion_browser_qa_report.json")) if MOTION_QA_ARTIFACT_ROOT.exists() else []
    legacy_v1_report_count = sum(
        1
        for path in report_paths
        if _read_next_session_browser_qa_report(path).get("schema_version") == "command_center_3_motion_browser_qa_result.v1"
    )
    expected_head_full = motion_evidence_service.current_repository_head(PROJECT_ROOT)
    validation = motion_evidence_service.validate_current_motion_evidence(
        MOTION_QA_ARTIFACT_ROOT.parent,
        expected_head_full=expected_head_full,
        project_root=PROJECT_ROOT,
    )
    verified = validation.get("motion_current_head_pair_verified") is True
    trusted_rows = _as_dict(validation.get("validated_route_rows")).get("#next-session-chart") if verified else []
    next_rows = []
    for row in _as_list(trusted_rows):
        if not isinstance(row, Mapping):
            continue
        transition_observed = row.get("route_transition_observed_us")
        transition_budget = row.get("route_transition_budget_us")
        performance_passed = bool(
            row.get("performance_trace_complete") is True
            and type(transition_observed) is int
            and type(transition_budget) is int
            and transition_observed <= transition_budget
            and row.get("long_task_over_50ms_count") == 0
        )
        visual_passed = row.get("visual_qa_complete") is True and row.get("status") == "passed"
        next_rows.append(
            {
                **dict(row),
                "performance_passed": performance_passed,
                "review_required": not (visual_passed and performance_passed),
                "reads_current_head_v6_validation_only": True,
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
        )
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
    local_evidence_found = verified and row_count == 8
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
        "scanned_report_count": len(report_paths),
        "valid_report_count": 2 if verified else 0,
        "legacy_v1_report_count": legacy_v1_report_count,
        "legacy_v1_compatibility_status": "blocked_not_promotion_evidence" if legacy_v1_report_count else "not_present",
        "next_report_count": 2 if verified else 0,
        "report_count": 2 if verified else 0,
        "passing_report_count": 2 if evidence_ready else 0,
        "next_route": "#next-session-chart",
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
        "latest_report_path": None,
        "latest_run_id": validation.get("normal_run_id"),
        "latest_generated_at": None,
        "current_head_full": expected_head_full,
        "current_head_motion_validation_status": validation.get("status"),
        "current_head_motion_validation_blockers": _as_list(validation.get("blockers")),
        "row_count": row_count,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": False,
        "reads_current_head_terminal_v6_pair_only": True,
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
        "note": "Only validate_current_motion_evidence current-head terminal v6 normal/reduced rows can advance review. Legacy v1 reports are compatibility-visible but always blocked.",
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
            evidence="next_session_browser_qa_evidence_summary found ignored local runner rows for #next-session-chart.",
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
        "next_route": "#next-session-chart",
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
        "note": "This review promotes local #next-session-chart browser QA evidence only to a button-gated local review state. It does not execute browser QA, prove legacy signal/capability parity, or complete production replacement.",
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
    if not SQLITE_META_PATH.exists():
        return {}
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


def _next_session_streamlit_parity_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    next_action: str,
    feature_group: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocking": not bool(passed),
        "feature_group": feature_group,
        "evidence": evidence,
        "next_action": next_action,
        "review_only": True,
        "same_packet_review": True,
        "streamlit_reference_captured": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "opens_no_streamlit": True,
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


def _next_session_same_packet_signal_capability_coverage(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Observe retained Next Session signal/capability fields in one packet.

    This is deliberately a read-only inspection of the exact ECharts payload.
    It does not compare or launch the legacy UI, call a provider/model, or
    promote the replacement.  A later explicit parity-review POST binds this
    observation to a review task.
    """
    chart = _as_dict(packet.get("chart_payload"))
    chart_summary = _as_dict(packet.get("chart_summary")) or _as_dict(chart.get("chart_summary"))
    chart_contract = _as_dict(chart.get("chart_contract"))
    interaction_audit = _as_dict(chart.get("interaction_readiness_audit"))
    data_trust = _as_dict(chart.get("data_trust_summary")) or _as_dict(packet.get("data_trust_summary"))
    position_conflict = _as_dict(chart.get("position_conflict")) or _as_dict(packet.get("position_context"))
    lineage = _as_dict(packet.get("candidate_radar_v05_lineage"))
    chart_source_task_id = _safe_text(chart.get("source_task_id") or "", limit=128)
    chart_result_version = _safe_text(chart.get("result_version") or "", limit=128)
    chart_data_date = _safe_text(chart.get("data_date") or packet.get("data_date") or "", limit=32)
    lineage_bound = True
    if lineage.get("status") == "same_packet_lineage_ready":
        lineage_bound = bool(
            chart_source_task_id
            and chart_result_version
            and chart_source_task_id == _safe_text(lineage.get("candidate_task_id") or "", limit=128)
            and chart_result_version == _safe_text(lineage.get("candidate_result_version") or "", limit=128)
            and chart_data_date == _safe_text(lineage.get("data_date") or "", limit=32)
        )

    rows = [
        {
            "coverage_key": "latest_close_anchor",
            "label": "latest close anchor",
            "retained": bool(_as_dict(chart.get("latest_close_anchor")).get("price") is not None),
            "source": "chart_payload.latest_close_anchor",
        },
        {
            "coverage_key": "scenario_paths",
            "label": "scenario paths",
            "retained": bool(_as_list(chart.get("scenario_series")) and _as_list(chart.get("scenario_anchor_rows"))),
            "source": "chart_payload.scenario_series/scenario_anchor_rows",
        },
        {
            "coverage_key": "reference_and_limit_lines",
            "label": "reference and limit lines",
            "retained": bool(_as_list(chart.get("reference_line_rows")) and _as_list(chart.get("reference_lines"))),
            "source": "chart_payload.reference_line_rows/reference_lines",
        },
        {
            "coverage_key": "operation_zones_and_guardrails",
            "label": "operation zones and guardrails",
            "retained": bool(
                _as_list(chart.get("zone_interaction_rows"))
                and all(row.get("frontend_mutable") is False for row in _as_list(chart.get("zone_interaction_rows")) if isinstance(row, dict))
            ),
            "source": "chart_payload.zone_interaction_rows",
        },
        {
            "coverage_key": "position_conflict_warnings",
            "label": "position conflict warnings",
            "retained": bool(position_conflict),
            "source": "chart_payload.position_conflict/position_context",
        },
        {
            "coverage_key": "freshness_and_data_trust",
            "label": "freshness and data trust",
            "retained": bool(data_trust and (_as_list(data_trust.get("facts")) or packet.get("freshness_state"))),
            "source": "chart_payload.data_trust_summary + packet.freshness_state",
        },
        {
            "coverage_key": "deepseek_status_display",
            "label": "DeepSeek status display",
            "retained": bool(chart.get("deepseek_status") or _as_dict(data_trust.get("deepseek")).get("status")),
            "source": "chart_payload.deepseek_status/data_trust_summary.deepseek",
        },
        {
            "coverage_key": "hover_click_drilldown",
            "label": "hover and click drilldown",
            "retained": bool(
                interaction_audit.get("schema_version") == "next_session_interaction_readiness.v1"
                and int(interaction_audit.get("blocking_count") or 0) == 0
            ),
            "source": "chart_payload.interaction_readiness_audit",
        },
        {
            "coverage_key": "read_only_action_boundary",
            "label": "read-only action boundary",
            "retained": bool(
                chart_contract.get("cache_only") is True
                and chart_contract.get("frontend_computes_trade_action") is False
                and chart_contract.get("does_not_modify_action") is True
                and chart_contract.get("does_not_modify_operation_zones") is True
            ),
            "source": "chart_payload.chart_contract",
        },
    ]
    missing = [str(row["coverage_key"]) for row in rows if row.get("retained") is not True]
    packet_safe = (
        packet.get("external_calls_triggered") is not True
        and packet.get("tushare_called") is not True
        and packet.get("deepseek_called") is not True
        and packet.get("github_called") is not True
        and packet.get("does_not_execute_trades") is not False
        and packet.get("does_not_modify_strategy_action") is not False
    )
    direct_evidence_ready = bool(
        packet_safe
        and chart.get("is_exact_next_session_packet") is True
        and chart_summary.get("has_drawable_data") is True
        and not missing
        and lineage_bound
    )
    for row in rows:
        row.update(
            {
                "direct_observation": True,
                "same_packet": True,
                "review_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_operation_zones": True,
                "contains_secret": False,
            }
        )
    return {
        "schema_version": "next_session_same_packet_signal_capability_coverage.v1",
        "status": "same_packet_signal_capability_coverage_ready" if direct_evidence_ready else "same_packet_signal_capability_coverage_pending",
        "scope": "exact_next_session_echarts_packet_same_packet_signal_capability_observation",
        "same_packet": True,
        "lineage_bound": lineage_bound,
        "direct_observation": True,
        "direct_evidence_ready": direct_evidence_ready,
        "required_feature_group_count": len(rows),
        "retained_feature_group_count": len(rows) - len(missing),
        "missing_feature_groups": missing,
        "rows": rows,
        "row_count": len(rows),
        "packet_safe": packet_safe,
        "streamlit_reference_captured": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
    }


def _next_session_streamlit_parity_review_contract(
    parity_recipe: Mapping[str, Any],
    parity_rows: list[Mapping[str, Any]],
    *,
    explicit_review: bool = False,
    task_id: str = "",
    reviewed_at: str = "",
    retained_coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows_by_phase = {
        str(row.get("phase")): row for row in parity_rows if isinstance(row, Mapping) and row.get("phase")
    }
    preserved_groups = set(_as_list(parity_recipe.get("preserved_feature_groups")))
    required_groups = {
        "latest close anchor",
        "scenario paths",
        "reference and limit lines",
        "operation zones and guardrails",
        "position conflict warnings",
        "freshness and data trust",
        "DeepSeek status display",
        "hover and click drilldown",
        "read-only action boundary",
    }
    cache_payload_ready = rows_by_phase.get("cache_payload_snapshot", {}).get("local_ready") is True
    feature_matrix_ready = rows_by_phase.get("chart_visual_feature_matrix", {}).get("local_ready") is True
    zone_guardrail_ready = rows_by_phase.get("operation_zone_and_guardrail_parity", {}).get("local_ready") is True
    context_ready = rows_by_phase.get("position_conflict_and_data_trust_parity", {}).get("local_ready") is True
    hover_click_ready = rows_by_phase.get("hover_click_interaction_parity", {}).get("local_ready") is True
    read_only_ready = rows_by_phase.get("frontend_read_only_no_feature_loss_boundary", {}).get("local_ready") is True
    no_group_loss_ready = required_groups.issubset(preserved_groups)
    retained_coverage_map = _as_dict(retained_coverage)
    retained_coverage_ready = (
        retained_coverage_map.get("direct_evidence_ready") is True
        if retained_coverage is not None
        else no_group_loss_ready
    )
    rows = [
        _next_session_streamlit_parity_review_row(
            "explicit_post_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            passed=explicit_review,
            evidence=f"task_id={task_id or 'not_started'}; reviewed_at={reviewed_at or 'not_reviewed'}",
            next_action="Run the explicit POST review before treating same-packet parity evidence as direct.",
            feature_group="button-gated review",
        ),
        _next_session_streamlit_parity_review_row(
            "exact_cache_payload_snapshot_ready",
            "passed" if cache_payload_ready else "blocked_exact_packet",
            passed=cache_payload_ready,
            evidence=str(rows_by_phase.get("cache_payload_snapshot", {}).get("evidence", "")),
            next_action="Keep the exact React/ECharts packet available for same-packet review.",
            feature_group="exact ECharts packet",
        ),
        _next_session_streamlit_parity_review_row(
            "legacy_reference_capture_stays_pending",
            "passed_reference_capture_not_claimed",
            passed=True,
            evidence="This local review intentionally does not claim a captured Streamlit screenshot or reference packet.",
            next_action="Capture legacy Streamlit reference separately before production replacement.",
            feature_group="legacy reference baseline",
        ),
        _next_session_streamlit_parity_review_row(
            "chart_visual_feature_matrix_reviewed",
            "passed" if feature_matrix_ready else "blocked_feature_matrix",
            passed=feature_matrix_ready,
            evidence=str(rows_by_phase.get("chart_visual_feature_matrix", {}).get("evidence", "")),
            next_action="Compare latest close, scenarios, reference lines, zones, data trust, and DeepSeek status against legacy behavior.",
            feature_group="visual signal groups",
        ),
        _next_session_streamlit_parity_review_row(
            "operation_zone_and_guardrail_reviewed",
            "passed" if zone_guardrail_ready else "blocked_operation_zone_guardrail",
            passed=zone_guardrail_ready,
            evidence=str(rows_by_phase.get("operation_zone_and_guardrail_parity", {}).get("evidence", "")),
            next_action="Keep operation-zone labels, ranges, and guardrails visible without frontend mutation.",
            feature_group="operation zones and guardrails",
        ),
        _next_session_streamlit_parity_review_row(
            "position_conflict_and_data_trust_reviewed",
            "passed" if context_ready else "blocked_context_review",
            passed=context_ready,
            evidence=str(rows_by_phase.get("position_conflict_and_data_trust_parity", {}).get("evidence", "")),
            next_action="Keep conflict warnings, freshness/data trust, and model/provider status visible.",
            feature_group="position and data trust context",
        ),
        _next_session_streamlit_parity_review_row(
            "hover_click_contract_reviewed",
            "passed" if hover_click_ready else "blocked_hover_click_contract",
            passed=hover_click_ready,
            evidence=str(rows_by_phase.get("hover_click_interaction_parity", {}).get("evidence", "")),
            next_action="Capture hover/click parity notes against the legacy UI before production replacement.",
            feature_group="hover/click/source display",
        ),
        _next_session_streamlit_parity_review_row(
            "frontend_read_only_boundary_reviewed",
            "passed" if read_only_ready else "blocked_frontend_read_only_boundary",
            passed=read_only_ready,
            evidence=str(rows_by_phase.get("frontend_read_only_no_feature_loss_boundary", {}).get("evidence", "")),
            next_action="Keep React/ECharts render-only; do not compute action or mutate operation zones.",
            feature_group="read-only frontend boundary",
        ),
        _next_session_streamlit_parity_review_row(
            "no_feature_group_dropped",
            "passed" if no_group_loss_ready else "blocked_feature_group_loss",
            passed=no_group_loss_ready,
            evidence=f"preserved_feature_groups={len(preserved_groups)}; required_feature_groups={len(required_groups)}",
            next_action="Do not remove legacy signal groups to make the migration easier.",
            feature_group="feature parity inventory",
        ),
        _next_session_streamlit_parity_review_row(
            "production_replacement_stays_blocked",
            "passed",
            passed=True,
            evidence="Same-packet local review is not durable CI/release evidence and does not remove Streamlit fallback.",
            next_action="Require durable browser/release evidence and explicit promotion before replacement.",
            feature_group="production boundary",
        ),
    ]
    blocking_rows = [row["criterion"] for row in rows if row["blocking"]]
    same_packet_ready = explicit_review and not blocking_rows
    same_packet_ready = same_packet_ready and retained_coverage_ready
    status = (
        "next_session_streamlit_parity_review_ready_local_same_packet"
        if same_packet_ready
        else "next_session_streamlit_parity_review_pending"
    )
    return {
        "schema_version": "next_session_streamlit_parity_review.v1",
        "status": status,
        "scope": "button_gated_local_next_session_streamlit_parity_review_no_streamlit_no_browser_no_provider",
        "ltg": "LTG-08/LTG-10",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": bool(explicit_review),
        "local_streamlit_parity_review_ready": same_packet_ready,
        "same_packet_no_loss_review_ready": same_packet_ready,
        "same_packet_signal_capability_coverage_reviewed": bool(retained_coverage_ready and explicit_review),
        "same_packet_signal_capability_coverage": retained_coverage_map,
        "feature_by_feature_parity_reviewed": same_packet_ready,
        "hover_click_parity_reviewed": same_packet_ready and hover_click_ready,
        "streamlit_reference_captured": False,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "legacy_fallback_removed": False,
        "no_feature_loss_required": True,
        "preserved_feature_groups": sorted(preserved_groups),
        "required_feature_groups": sorted(required_groups),
        "review_row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "blocking_review_rows": blocking_rows,
        "rows": rows,
        "opens_no_streamlit": True,
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
        "note": "This is a button-gated same-packet no-feature-loss review. It does not start Streamlit, capture a Streamlit reference, run browser QA, remove fallback, or complete production replacement.",
    }


def _safe_persisted_streamlit_parity_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    review = _as_dict(packet.get("next_session_streamlit_parity_review_contract"))
    safe = (
        review.get("schema_version") == "next_session_streamlit_parity_review.v1"
        and review.get("scope")
        == "button_gated_local_next_session_streamlit_parity_review_no_streamlit_no_browser_no_provider"
        and review.get("explicit_review_task_done") is True
        and review.get("local_streamlit_parity_review_ready") is True
        and review.get("same_packet_no_loss_review_ready") is True
        and review.get("streamlit_reference_captured") is False
        and review.get("streamlit_parity_complete") is False
        and review.get("production_replacement_complete") is False
        and review.get("opens_no_streamlit") is True
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


def _read_next_session_streamlit_parity_review_packet() -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {}
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(NEXT_SESSION_STREAMLIT_PARITY_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_streamlit_parity_review(packet) else {}


def _write_next_session_streamlit_parity_review_packet(
    *,
    review_contract: Mapping[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": NEXT_SESSION_STREAMLIT_PARITY_REVIEW_PACKET_KEY,
        "schema_version": "next_session_streamlit_parity_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-08/LTG-10",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "next_session_streamlit_parity_review_contract": dict(review_contract),
        "next_session_streamlit_parity_review_rows": _as_list(review_contract.get("rows")),
        "call_ledger": list(ledger),
        "cache_only": True,
        "opens_no_streamlit": True,
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
            "This packet is a local same-packet legacy signal/capability parity/no-feature-loss review receipt only.",
            "It does not open Streamlit or a browser, call providers/models/GitHub, execute trades, remove fallback, mutate action or operation zones, or complete production replacement.",
        ],
    }
    if _safe_persisted_streamlit_parity_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(NEXT_SESSION_STREAMLIT_PARITY_REVIEW_PACKET_KEY, packet)


def _next_session_production_promotion_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    blocking: bool,
    evidence: str,
    next_action: str,
    evidence_group: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocking": bool(blocking),
        "evidence_group": evidence_group,
        "evidence": evidence,
        "next_action": next_action,
        "review_only": True,
        "promotion_review": True,
        "production_replacement_complete": False,
        "ready_to_mark_production_replacement_complete": False,
        "streamlit_parity_complete": False,
        "durable_ci_evidence_complete": False,
        "opens_no_streamlit": True,
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


def _next_session_production_promotion_review_contract(
    packet: Mapping[str, Any],
    *,
    explicit_review: bool = False,
    task_id: str = "",
    reviewed_at: str = "",
) -> dict[str, Any]:
    browser_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    streamlit_review = _as_dict(packet.get("next_session_streamlit_parity_review_contract"))
    durable_recipe = _as_dict(packet.get("next_session_durable_evidence_recipe"))
    activation = _as_dict(packet.get("next_session_replacement_activation_receipt"))

    browser_ready = (
        browser_review.get("local_browser_qa_review_ready") is True
        and browser_review.get("next_visual_qa_evidence_passed") is True
        and browser_review.get("next_browser_performance_evidence_passed") is True
        and browser_review.get("default_motion_passed") is True
        and browser_review.get("reduced_motion_passed") is True
        and browser_review.get("motion_viewport_coverage_complete") is True
        and browser_review.get("production_replacement_complete") is False
    )
    streamlit_ready = (
        streamlit_review.get("schema_version") == "next_session_streamlit_parity_review.v1"
        and streamlit_review.get("local_streamlit_parity_review_ready") is True
        and streamlit_review.get("same_packet_no_loss_review_ready") is True
        and streamlit_review.get("streamlit_reference_captured") is False
        and streamlit_review.get("streamlit_parity_complete") is False
        and streamlit_review.get("production_replacement_complete") is False
    )
    durable_recipe_ready = (
        durable_recipe.get("schema_version") == NEXT_SESSION_DURABLE_EVIDENCE_SCHEMA_VERSION
        and durable_recipe.get("local_recipe_ready") is True
        and durable_recipe.get("production_replacement_complete") is False
        and durable_recipe.get("durable_promotion_ready") is False
    )
    durable_ci_complete = durable_recipe.get("durable_ci_evidence_complete") is True
    production_replacement_complete = activation.get("production_replacement_complete") is True
    boundary_ready = (
        browser_review.get("external_calls_triggered") is False
        and streamlit_review.get("external_calls_triggered") is False
        and durable_recipe.get("external_calls_triggered") is False
        and browser_review.get("tushare_called") is False
        and streamlit_review.get("tushare_called") is False
        and durable_recipe.get("tushare_called") is False
        and browser_review.get("deepseek_called") is False
        and streamlit_review.get("deepseek_called") is False
        and durable_recipe.get("deepseek_called") is False
        and browser_review.get("github_called") is False
        and streamlit_review.get("github_called") is False
        and durable_recipe.get("github_called") is False
        and browser_review.get("does_not_execute_trades") is True
        and streamlit_review.get("does_not_execute_trades") is True
        and durable_recipe.get("does_not_execute_trades") is True
        and browser_review.get("does_not_modify_strategy_action") is True
        and streamlit_review.get("does_not_modify_strategy_action") is True
        and durable_recipe.get("does_not_modify_strategy_action") is True
        and browser_review.get("does_not_modify_operation_zones") is True
        and streamlit_review.get("does_not_modify_operation_zones") is True
        and durable_recipe.get("does_not_modify_operation_zones") is True
    )
    rows = [
        _next_session_production_promotion_review_row(
            "explicit_post_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            passed=explicit_review,
            blocking=not explicit_review,
            evidence=f"task_id={task_id or 'not_started'}; reviewed_at={reviewed_at or 'not_reviewed'}",
            next_action="Run the explicit POST promotion review before moving the promotion stage out of pending.",
            evidence_group="button-gated promotion review",
        ),
        _next_session_production_promotion_review_row(
            "local_browser_visual_performance_review_visible",
            "passed" if browser_ready else "blocked_browser_visual_performance_review",
            passed=browser_ready,
            blocking=not browser_ready,
            evidence=(
                f"local_browser_qa_review_ready={browser_review.get('local_browser_qa_review_ready') is True}; "
                f"visual={browser_review.get('next_visual_qa_evidence_passed')}; "
                f"performance={browser_review.get('next_browser_performance_evidence_passed')}; "
                f"reduced_motion={browser_review.get('reduced_motion_passed')}"
            ),
            next_action="Keep browser visual/performance/reduced-motion evidence reviewed before promotion review.",
            evidence_group="browser QA local review",
        ),
        _next_session_production_promotion_review_row(
            "same_packet_streamlit_parity_review_visible",
            "passed" if streamlit_ready else "blocked_same_packet_parity_review",
            passed=streamlit_ready,
            blocking=not streamlit_ready,
            evidence=(
                f"same_packet_no_loss_review_ready={streamlit_review.get('same_packet_no_loss_review_ready') is True}; "
                f"streamlit_reference_captured={streamlit_review.get('streamlit_reference_captured') is True}; "
                f"streamlit_parity_complete={streamlit_review.get('streamlit_parity_complete') is True}"
            ),
            next_action="Keep same-packet no-feature-loss review ready without claiming captured legacy signal/capability parity.",
            evidence_group="legacy signal/capability parity local review",
        ),
        _next_session_production_promotion_review_row(
            "durable_evidence_recipe_visible",
            "passed" if durable_recipe_ready else "blocked_durable_recipe",
            passed=durable_recipe_ready,
            blocking=not durable_recipe_ready,
            evidence=(
                f"local_recipe_ready={durable_recipe.get('local_recipe_ready') is True}; "
                f"durable_promotion_ready={durable_recipe.get('durable_promotion_ready') is True}"
            ),
            next_action="Keep the durable evidence recipe visible before any release/promotion decision.",
            evidence_group="durable evidence recipe",
        ),
        _next_session_production_promotion_review_row(
            "durable_ci_release_evidence_still_required",
            "passed_durable_release_still_missing",
            passed=True,
            blocking=False,
            evidence=f"durable_ci_evidence_complete={durable_ci_complete}; local review does not create CI/release evidence.",
            next_action="Attach real durable CI/release evidence separately before production replacement.",
            evidence_group="durable CI/release blocker",
        ),
        _next_session_production_promotion_review_row(
            "production_replacement_stays_blocked",
            "passed",
            passed=not production_replacement_complete,
            blocking=production_replacement_complete,
            evidence=(
                f"production_replacement_complete={production_replacement_complete}; "
                "promotion review is local evidence, not production replacement."
            ),
            next_action="Do not remove Streamlit fallback or mark ECharts production replacement complete from this receipt.",
            evidence_group="production boundary",
        ),
        _next_session_production_promotion_review_row(
            "no_provider_model_trade_action_secret_boundary",
            "passed" if boundary_ready else "blocked_boundary_regression",
            passed=boundary_ready,
            blocking=not boundary_ready,
            evidence="Browser, legacy signal/capability parity, and durable recipe inputs are local-only and read-only.",
            next_action="Keep provider/model/GitHub/trading calls out of cache/render and this local review task.",
            evidence_group="safety boundary",
        ),
    ]
    blocking_rows = [row["criterion"] for row in rows if row["blocking"]]
    local_review_ready = explicit_review and not blocking_rows
    status = (
        "next_session_production_promotion_review_ready_replacement_blocked"
        if local_review_ready
        else "next_session_production_promotion_review_pending"
    )
    production_blockers = [
        "durable_ci_release_evidence",
        "production_replacement_complete_false",
    ]
    return {
        "schema_version": NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_next_session_production_promotion_review_no_browser_no_provider",
        "ltg": "LTG-08/LTG-10",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": bool(explicit_review),
        "local_production_promotion_review_ready": local_review_ready,
        "ready_to_mark_production_replacement_complete": False,
        "production_replacement_complete": False,
        "durable_promotion_ready": False,
        "durable_ci_evidence_complete": False,
        "durable_ci_or_release_evidence_complete": False,
        "streamlit_parity_complete": False,
        "streamlit_reference_captured": False,
        "legacy_fallback_removed": False,
        "same_packet_no_loss_review_ready": streamlit_ready,
        "local_browser_qa_review_ready": browser_ready,
        "durable_evidence_recipe_ready": durable_recipe_ready,
        "review_row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "blocking_review_rows": blocking_rows,
        "production_blocker_count": len(production_blockers),
        "production_blocker_keys": production_blockers,
        "rows": rows,
        "opens_no_streamlit": True,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "contains_secret": False,
        "note": "This is a button-gated local promotion review. It records that local ECharts evidence is reviewed while durable CI/release evidence and production replacement remain blocked.",
    }


def _safe_persisted_production_promotion_review(packet: Mapping[str, Any]) -> dict[str, Any]:
    review = _as_dict(packet.get("next_session_production_promotion_review_contract"))
    safe = (
        review.get("schema_version") == NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION
        and review.get("scope")
        == "button_gated_local_next_session_production_promotion_review_no_browser_no_provider"
        and review.get("explicit_review_task_done") is True
        and review.get("local_production_promotion_review_ready") is True
        and review.get("ready_to_mark_production_replacement_complete") is False
        and review.get("production_replacement_complete") is False
        and review.get("durable_promotion_ready") is False
        and review.get("durable_ci_evidence_complete") is False
        and review.get("streamlit_parity_complete") is False
        and review.get("legacy_fallback_removed") is False
        and review.get("opens_no_streamlit") is True
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


def _read_next_session_production_promotion_review_packet() -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {}
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_production_promotion_review(packet) else {}


def _write_next_session_production_promotion_review_packet(
    *,
    review_contract: Mapping[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": "next_session_production_promotion_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-08/LTG-10",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "next_session_production_promotion_review_contract": dict(review_contract),
        "next_session_production_promotion_review_rows": _as_list(review_contract.get("rows")),
        "call_ledger": list(ledger),
        "cache_only": True,
        "opens_no_streamlit": True,
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
            "This packet is a local production-promotion review receipt only.",
            "It does not open Streamlit or a browser, call providers/models/GitHub, execute trades, remove fallback, mutate action or operation zones, or complete production replacement.",
        ],
    }
    if _safe_persisted_production_promotion_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY, packet)


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
            next_action="Run explicit legacy signal/capability parity review before claiming ECharts production replacement.",
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
            evidence="Legacy signal/capability parity, browser visual QA, performance trace, reduced-motion QA, and durable evidence are pending.",
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
        "note": "This local recipe fixes the no-feature-loss acceptance path for LTG-08. It does not execute browser QA, prove legacy signal/capability parity, or complete production replacement.",
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
    local_release_gate_receipt = _read_next_session_local_release_gate_receipt()
    local_release_gate_observed = local_release_gate_receipt.get("fresh_local_gate_run_observed") is True

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
            next_action="Use the parity recipe as a no-feature-loss checklist, not as completed legacy signal/capability parity.",
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
            (
                "completed"
                if durable_ci_evidence_complete
                else (
                    "local_release_gate_observed_remote_ci_pending"
                    if local_release_gate_observed
                    else "pending_durable_ci_release_evidence"
                )
            ),
            passed=durable_ci_evidence_complete,
            local_surface_required=False,
            production_blocker=not durable_ci_evidence_complete,
            evidence=(
                f"durable_ci_evidence_complete={durable_ci_evidence_complete}; "
                f"local_release_gate_observed={local_release_gate_observed}; "
                f"head_matches_current={local_release_gate_receipt.get('head_matches_current') is True}; "
                f"remote_actions_status_known={local_release_gate_receipt.get('remote_actions_status_known') is True}"
            ),
            next_action="Keep current-HEAD local gate evidence separate from remote CI/release evidence.",
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
        "local_release_gate_receipt": local_release_gate_receipt,
        "local_release_gate_evidence_observed": local_release_gate_observed,
        "local_release_gate_evidence_head_matches_current": local_release_gate_receipt.get("head_matches_current")
        is True,
        "local_release_gate_evidence_required_checks_present": local_release_gate_receipt.get(
            "required_local_gate_checks_present"
        )
        is True,
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
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
            "treat interaction readiness as legacy signal/capability parity",
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
        "note": "This recipe fixes the durable evidence checklist for LTG-08. It does not open a browser, start servers, call providers/models/GitHub, execute trades, mutate action or operation zones, prove legacy signal/capability parity, or complete ECharts production replacement.",
    }
    contract["call_ledger"] = [
        {
            "api": "local_next_session_durable_evidence_recipe",
            "request_params_safe": {
                "status": contract["status"],
                "row_count": len(rows),
                "production_blocker_count": len(durable_blockers),
                "local_release_gate_evidence_observed": local_release_gate_observed,
                "remote_actions_status_known": False,
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
    production_blocker: bool | None = None,
    current_status: str,
    evidence: str,
    missing_evidence: list[str],
    recommended_order: int,
) -> dict[str, Any]:
    blocker = not bool(direct_evidence_complete) if production_blocker is None else bool(production_blocker)
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
        "production_blocker": blocker,
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
    streamlit_review = _as_dict(packet.get("next_session_streamlit_parity_review_contract"))
    promotion_review = _as_dict(packet.get("next_session_production_promotion_review_contract"))
    activation = _as_dict(packet.get("next_session_replacement_activation_receipt"))
    local_release_gate_receipt = _read_next_session_local_release_gate_receipt()
    local_release_gate_observed = local_release_gate_receipt.get("fresh_local_gate_run_observed") is True

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
    streamlit_same_packet_review_ready = (
        streamlit_review.get("schema_version") == "next_session_streamlit_parity_review.v1"
        and streamlit_review.get("scope")
        == "button_gated_local_next_session_streamlit_parity_review_no_streamlit_no_browser_no_provider"
        and streamlit_review.get("local_streamlit_parity_review_ready") is True
        and streamlit_review.get("same_packet_no_loss_review_ready") is True
        and streamlit_review.get("streamlit_reference_captured") is False
        and streamlit_review.get("streamlit_parity_complete") is False
        and streamlit_review.get("production_replacement_complete") is False
    )
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
    production_promotion_review_ready = (
        promotion_review.get("schema_version") == NEXT_SESSION_PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION
        and promotion_review.get("scope")
        == "button_gated_local_next_session_production_promotion_review_no_browser_no_provider"
        and promotion_review.get("local_production_promotion_review_ready") is True
        and promotion_review.get("ready_to_mark_production_replacement_complete") is False
        and promotion_review.get("production_replacement_complete") is False
        and promotion_review.get("durable_ci_evidence_complete") is False
        and promotion_review.get("external_calls_triggered") is False
        and promotion_review.get("tushare_called") is False
        and promotion_review.get("deepseek_called") is False
        and promotion_review.get("github_called") is False
    )

    rows = [
        _next_session_production_stage_scope_row(
            "exact_cache_payload_contract",
            local_contract_ready=exact_payload_contract_ready,
            direct_evidence_complete=exact_payload_contract_ready,
            current_status=(
                "direct_evidence_ready_local_cache_contract"
                if exact_payload_contract_ready
                else "pending_exact_cache_payload"
            ),
            evidence=(
                f"chart_status={chart.get('status')}; exact={chart.get('is_exact_next_session_packet')}; "
                f"renderer={chart_contract.get('renderer')}"
            ),
            missing_evidence=[] if exact_payload_contract_ready else ["exact ECharts cache payload contract"],
            recommended_order=1,
        ),
        _next_session_production_stage_scope_row(
            "interaction_hover_click_contract",
            local_contract_ready=interaction_contract_ready,
            direct_evidence_complete=interaction_contract_ready,
            current_status=(
                "direct_evidence_ready_local_interaction_contract"
                if interaction_contract_ready
                else "pending_interaction_contract"
            ),
            evidence=(
                f"status={interaction_audit.get('status')}; "
                f"blocking_count={interaction_audit.get('blocking_count')}"
            ),
            missing_evidence=[] if interaction_contract_ready else ["hover/click interaction contract"],
            recommended_order=2,
        ),
        _next_session_production_stage_scope_row(
            "streamlit_parity_review",
            local_contract_ready=streamlit_same_packet_review_ready,
            direct_evidence_complete=streamlit_same_packet_review_ready,
            production_blocker=True,
            current_status=(
                "direct_evidence_ready_local_same_packet_no_loss_review_reference_pending"
                if streamlit_same_packet_review_ready
                else "pending_same_packet_streamlit_parity"
            ),
            evidence=(
                f"same_packet_no_loss_review_ready={streamlit_review.get('same_packet_no_loss_review_ready') is True}; "
                f"streamlit_reference_captured={streamlit_review.get('streamlit_reference_captured') is True}; "
                f"streamlit_parity_complete={activation.get('streamlit_parity_complete') is True}"
            ),
            missing_evidence=(
                ["legacy Streamlit reference capture", "durable CI/release evidence", "production replacement promotion"]
                if streamlit_same_packet_review_ready
                else ["explicit same-packet Streamlit reference capture", "feature-by-feature parity matrix"]
            ),
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
            local_contract_ready=local_release_gate_observed,
            direct_evidence_complete=local_release_gate_observed,
            production_blocker=True,
            current_status=(
                "direct_evidence_ready_local_gate_current_head_remote_ci_pending"
                if local_release_gate_observed
                else "pending_durable_ci_release_evidence"
            ),
            evidence=(
                f"local_release_gate_observed={local_release_gate_observed}; "
                f"head_matches_current={local_release_gate_receipt.get('head_matches_current') is True}; "
                f"required_checks_present={local_release_gate_receipt.get('required_local_gate_checks_present') is True}; "
                f"remote_actions_status_known={local_release_gate_receipt.get('remote_actions_status_known') is True}; "
                f"durable_ci_evidence_complete={activation.get('durable_ci_evidence_complete') is True}"
            ),
            missing_evidence=(
                ["matching remote Actions or release evidence", "production replacement gate remains blocked"]
                if local_release_gate_observed
                else [
                    "current-HEAD local push gate receipt",
                    "matching remote Actions or release evidence",
                    "production replacement gate remains blocked",
                ]
            ),
            recommended_order=7,
        ),
        _next_session_production_stage_scope_row(
            "production_replacement_promotion",
            local_contract_ready=production_promotion_review_ready,
            direct_evidence_complete=production_promotion_review_ready,
            production_blocker=True,
            current_status=(
                "direct_evidence_ready_local_promotion_review_durable_release_pending"
                if production_promotion_review_ready
                else "pending_production_replacement_promotion"
            ),
            evidence=(
                f"local_production_promotion_review_ready={production_promotion_review_ready}; "
                f"ready_to_mark_production_replacement_complete="
                f"{promotion_review.get('ready_to_mark_production_replacement_complete') is True}; "
                f"production_replacement_complete={activation.get('production_replacement_complete') is True}"
            ),
            missing_evidence=(
                ["durable CI or release evidence", "production replacement gate remains blocked"]
                if production_promotion_review_ready
                else ["explicit production replacement promotion review"]
            ),
            recommended_order=8,
        ),
    ]
    direct_stage_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is True]
    pending_stage_keys = [row["stage_key"] for row in rows if row["direct_evidence_complete"] is not True]
    production_blocker_keys = [row["stage_key"] for row in rows if row["production_blocker"] is True]
    local_contract_stage_keys = [row["stage_key"] for row in rows if row["local_contract_ready"] is True]
    manifest = {
        "schema_version": NEXT_SESSION_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION,
        "status": "next_session_production_stage_scope_manifest_ready_production_pending",
        "scope": "next_session_production_replacement_stage_scope_manifest",
        "ltg": "LTG-08/LTG-10",
        "local_manifest_ready": True,
        "stage_count": len(rows),
        "direct_evidence_stage_count": len(direct_stage_keys),
        "pending_stage_count": len(pending_stage_keys),
        "production_blocker_count": len(production_blocker_keys),
        "stage_keys": list(NEXT_SESSION_PRODUCTION_STAGE_KEYS),
        "direct_evidence_stage_keys": direct_stage_keys,
        "pending_stage_keys": pending_stage_keys,
        "production_blocker_stage_keys": production_blocker_keys,
        "local_contract_stage_keys": local_contract_stage_keys,
        "exact_cache_payload_contract_done": exact_payload_contract_ready,
        "interaction_hover_click_contract_done": interaction_contract_ready,
        "browser_visual_qa_done": browser_visual_done,
        "browser_performance_trace_done": browser_performance_done,
        "reduced_motion_accessibility_qa_done": reduced_motion_done,
        "local_browser_qa_review_ready": local_review_ready,
        "local_streamlit_parity_review_ready": streamlit_same_packet_review_ready,
        "local_production_promotion_review_ready": production_promotion_review_ready,
        "local_release_gate_receipt": local_release_gate_receipt,
        "local_release_gate_evidence_observed": local_release_gate_observed,
        "local_release_gate_evidence_head_matches_current": local_release_gate_receipt.get("head_matches_current")
        is True,
        "local_release_gate_evidence_required_checks_present": local_release_gate_receipt.get(
            "required_local_gate_checks_present"
        )
        is True,
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
        "same_packet_no_loss_review_ready": streamlit_same_packet_review_ready,
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
        "note": "This manifest makes LTG-08 stage evidence visible from GET cache and React. It does not run browser QA, call providers/models/GitHub, execute trades, prove legacy signal/capability parity, or complete production replacement.",
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


def _next_session_ordinary_result_replay(packet: Mapping[str, Any]) -> dict[str, Any]:
    chart_payload = _as_dict(packet.get("chart_payload"))
    chart_summary = _as_dict(packet.get("chart_summary")) or _as_dict(chart_payload.get("chart_summary"))
    candidate_handoff = _as_dict(packet.get("candidate_radar_p3_handoff"))
    latest_close_anchor = _as_dict(chart_payload.get("latest_close_anchor"))
    has_drawable_data = chart_summary.get("has_drawable_data") is True
    candidate_p2_ready = candidate_handoff.get("p2_small_data_ready") is True
    candidate_readable = candidate_handoff.get("p3_readable_result_ready") is True or candidate_p2_ready
    confirmed_symbol = _safe_text(
        candidate_handoff.get("symbol") or packet.get("latest_confirmed_symbol") or "",
        limit=32,
    ).upper()
    confirmed_source_task_id = _safe_text(
        candidate_handoff.get("source_task_id") or packet.get("latest_confirmed_task_id") or "",
        limit=128,
    )
    chart_symbol = _safe_text(
        chart_summary.get("symbol")
        or chart_summary.get("ts_code")
        or chart_summary.get("confirmed_symbol")
        or chart_payload.get("symbol")
        or chart_payload.get("ts_code")
        or chart_payload.get("confirmed_symbol")
        or packet.get("symbol")
        or packet.get("ts_code")
        or "",
        limit=32,
    ).upper()
    chart_source_task_id = _safe_text(
        chart_payload.get("source_task_id") or packet.get("source_task_id") or "",
        limit=128,
    )
    chart_source_task_matches_confirmed = (
        True
        if not (candidate_readable and confirmed_source_task_id)
        else chart_source_task_id == confirmed_source_task_id
    )
    chart_symbol_matches_confirmed = (
        bool(has_drawable_data)
        if not (candidate_readable and confirmed_symbol)
        else bool(chart_symbol and chart_symbol == confirmed_symbol and chart_source_task_matches_confirmed)
    )
    chart_ready_for_confirmed_symbol = has_drawable_data and chart_symbol_matches_confirmed
    chart_stale_for_confirmed_symbol = has_drawable_data and candidate_readable and not chart_symbol_matches_confirmed
    uses_real_daily_close = chart_summary.get("uses_real_daily_close") is True
    exact_packet = chart_summary.get("is_exact_next_session_packet") is True
    scenario_count = int(chart_summary.get("scenario_series_count") or 0)
    reference_count = int(chart_summary.get("reference_line_count") or 0)
    operation_zone_count = int(chart_summary.get("operation_zone_count") or 0)
    latest_close = latest_close_anchor.get("price")
    last_cache = "；".join(
        item
        for item in [
            str(packet.get("cache_source") or "cache source unknown"),
            f"情景={scenario_count} / 参考线={reference_count} / 操作区={operation_zone_count}" if has_drawable_data else "",
            f"latest close={latest_close}" if latest_close else "",
            (
                f"图谱标的={chart_symbol or '未标记'} / 当前确认标的={confirmed_symbol}; "
                f"图谱任务={chart_source_task_id or '未标记'} / 当前任务={confirmed_source_task_id}"
            )
            if chart_stale_for_confirmed_symbol
            else "",
        ]
        if item
    ) or "暂无最近可用缓存"
    result_status = (
        "ready_cache_replay"
        if chart_ready_for_confirmed_symbol
        else "candidate_readable_result_replay_chart_pending"
        if candidate_readable
        else "waiting_for_cache_or_manual_task"
    )
    result_rows = [
        {
            "step": "1",
            "surface": "下一票雷达",
            "readable_result": (
                f"上游结果可读：{candidate_handoff.get('symbol') or '已确认标的'}"
                if candidate_readable
                else "可从已确认标的继续复核"
                if chart_ready_for_confirmed_symbol
                else "先回到雷达输入代码并点击确认"
            ),
            "evidence": (
                f"source_task={candidate_handoff.get('source_task_id') or 'candidate_radar_cache'}; "
                f"packet={CANDIDATE_RADAR_PACKET_KEY}"
                if candidate_readable
                else "候选池和搜票确认按钮在 #candidates；本页不扫描、不搜票。"
            ),
            "next_step": (
                "先读已确认标的和 Tushare-first 结论；完整图谱仍需手动生成。"
                if candidate_readable
                else "需要新标的时回到下一票雷达确认代码。"
            ),
            "boundary": "输入和页面打开不外联；只有确认按钮可创建 Tushare-first 后台 task。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "step": "2",
            "surface": "股票量化推演",
            "readable_result": (
                "上游 Tushare daily close 已在本地缓存参与图谱"
                if chart_ready_for_confirmed_symbol and uses_real_daily_close
                else str(candidate_handoff.get("ordinary_result_summary"))
                if candidate_readable
                else "等待上游 Tushare ledger 或本地阻断回放"
            ),
            "evidence": (
                "真实 daily close 已在本地缓存"
                if chart_ready_for_confirmed_symbol and uses_real_daily_close
                else f"Tushare-first {candidate_handoff.get('provider_api_success_count')}/{candidate_handoff.get('provider_api_call_count')} 个接口已回放"
                if candidate_p2_ready
                else "待 Tushare/cache 补证"
            ),
            "next_step": str(
                candidate_handoff.get("ordinary_result_next_step")
                or "先看支持/压制摘要，再回到次日图谱复核路径和操作区。"
            ),
            "boundary": "本页只读 cache，不补调 Tushare 或 DeepSeek；DeepSeek governed executor 单独补。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "step": "3",
            "surface": "次日图谱",
            "readable_result": (
                f"情景={scenario_count} / 参考线={reference_count} / 操作区={operation_zone_count}"
                if chart_ready_for_confirmed_symbol
                else "上游结果可读；完整 next-session 图谱待手动生成。"
                if candidate_readable
                else "暂无可绘制图谱；可手动生成本地任务。"
            ),
            "evidence": last_cache,
            "next_step": (
                "先看图表路径、参考线和操作区，再看缺少证据；工程审计在开发详情"
                if has_drawable_data
                else "点击本页生成任务，使用上游已确认标的创建本地图谱 cache。"
                if candidate_readable
                else "先点击生成任务或查看缓存状态；有图表后再按路径、参考线、操作区复核"
            ),
            "boundary": "operation_zones 只表示条件区间和复核提示；不是买卖指令，不写交易动作，不改 strategy action",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
    ]
    chart_review_rows = [
        {
            "复核项": "图表路径",
            "看什么": (
                f"情景路径 {scenario_count} 条；先看基准、乐观和压力路径的方向"
                if chart_ready_for_confirmed_symbol
                else "已有上游结论，但当前确认标的的图谱待手动生成"
                if chart_stale_for_confirmed_symbol
                else "暂无可绘制路径；先看缓存状态或点击生成任务"
            ),
            "证据": last_cache,
            "边界": "只读取图表路径；不重算价格、不调用数据源或模型",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "复核项": "参考线",
            "看什么": (
                f"参考线 {reference_count} 条；用于定位压力、支撑和最新收盘锚点"
                if chart_ready_for_confirmed_symbol
                else "等待当前确认标的的 reference_lines 写入本地 cache"
            ),
            "证据": f"latest close={latest_close}" if latest_close else "等待 latest close anchor",
            "边界": "参考线只作研究复核，不生成买卖动作",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "复核项": "操作区",
            "看什么": (
                f"操作区 {operation_zone_count} 个；只看条件区间、触发条件和风险提示"
                if chart_ready_for_confirmed_symbol
                else "等待当前确认标的的 operation_zones cache"
            ),
            "证据": "operation_zones 只表示条件区间和复核提示；不是买卖指令，不写交易动作，不改 strategy action",
            "边界": "不改 operation_zones、不下单、不写 strategy action",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "复核项": "缺少证据",
            "看什么": (
                "当前摘要未标记缺口"
                if exact_packet and chart_ready_for_confirmed_symbol
                else "完整 next-session 图谱待手动生成；上游 Tushare-first 可读结论已回放"
                if candidate_readable
                else "真实 close、精确 packet 或生产替代证据仍待补齐"
            ),
            "证据": (
                f"candidate_p3={candidate_handoff.get('status')}"
                if candidate_readable
                else "replacement / browser QA / retained signal / real close evidence"
            ),
            "边界": "缺口只提示后续补证，不把空结果解释成无风险",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
    ]
    boundary_normal = (
        packet.get("does_not_modify_action") is not False
        and packet.get("does_not_modify_operation_zones") is not False
    )
    condition_quick_read_rows = [
        {
            "速读项": "1. 来源",
            "当前状态": (
                "精确 next-session cache 可回放"
                if exact_packet and chart_ready_for_confirmed_symbol
                else "上游搜票结论可读；完整图谱等待手动生成"
                if candidate_readable
                else "等待精确 next-session cache 或按钮任务结果"
            ),
            "用户下一步": "先确认来源来自雷达/量化后的本地回放，再进入图表路径。",
            "边界": "只读 GET cache；页面打开、普通链接和 React render 不创建 task。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "速读项": "2. 条件",
            "当前状态": (
                f"operation_zones {operation_zone_count} 个；只表示条件区间、触发条件和风险提示"
                if chart_ready_for_confirmed_symbol
                else "等待 operation_zones cache；不能把空操作区解释成无风险"
            ),
            "用户下一步": "把操作区当人工复核条件，结合参考线和最新收盘锚点判断。",
            "边界": "operation_zones 不是买卖指令，不写交易动作，不改 strategy action。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "速读项": "3. 失效",
            "当前状态": (
                "当前摘要未标记关键缺口"
                if exact_packet and chart_ready_for_confirmed_symbol
                else "operation_zones cache 待生成；不要把上游可读结论当完整图谱"
                if candidate_readable
                else "真实 close、精确 packet 或 operation_zones cache 待补齐"
            ),
            "用户下一步": "缺口回到下一票雷达或股票量化推演补证；不要把空图谱解释成无风险。",
            "边界": "失效提示不自动重试、不补调 Tushare/DeepSeek/GitHub、不写 cache。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
        {
            "速读项": "4. 动作隔离",
            "当前状态": "边界正常：前端只读，不改 action 或 operation_zones" if boundary_normal else "边界异常：先停在审计检查",
            "用户下一步": "继续人工复核；需要刷新时只用按钮门控 POST task。",
            "边界": "次日图谱不下单、不写 strategy action；DeepSeek 也不能覆盖 operation_zones。",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        },
    ]
    return {
        "schema_version": "next_session_ordinary_result_replay.v1",
        "status": result_status,
        "source": "GET /api/next-session/cache",
        "row_count": len(result_rows),
        "chart_review_row_count": len(chart_review_rows),
        "condition_quick_read_row_count": len(condition_quick_read_rows),
        "rows_are_cache_only": True,
        "rows_create_task": False,
        "rows_call_provider_or_model": False,
        "rows_are_not_trade_signals": True,
        "contains_secret": False,
        "production_evidence": False,
        "confirmed_symbol": confirmed_symbol,
        "confirmed_source_task_id": confirmed_source_task_id,
        "chart_symbol": chart_symbol,
        "chart_source_task_id": chart_source_task_id,
        "chart_has_drawable_data": has_drawable_data,
        "chart_symbol_matches_confirmed": chart_symbol_matches_confirmed,
        "chart_source_task_matches_confirmed": chart_source_task_matches_confirmed,
        "chart_ready_for_confirmed_symbol": chart_ready_for_confirmed_symbol,
        "chart_stale_for_confirmed_symbol": chart_stale_for_confirmed_symbol,
        "result_rows": result_rows,
        "chart_review_rows": chart_review_rows,
        "condition_quick_read_rows": condition_quick_read_rows,
        **_local_ledger_boundary(),
    }


@memoize_request_local_read("next_session_cache")
def read_next_session_cache() -> dict[str, Any]:
    _sync_packet_service_sqlite_path()
    packet = dict(packet_service.build_next_session_cache())
    chart_payload_for_handoff = _as_dict(packet.get("chart_payload"))
    chart_summary_for_handoff = _as_dict(packet.get("chart_summary")) or _as_dict(
        chart_payload_for_handoff.get("chart_summary")
    )
    candidate_radar_p3_handoff = _read_candidate_radar_p3_handoff(
        chart_source_task_id=_safe_text(
            chart_payload_for_handoff.get("source_task_id") or packet.get("source_task_id") or "",
            limit=128,
        ),
        chart_result_version=_safe_text(
            chart_payload_for_handoff.get("result_version") or packet.get("result_version") or "",
            limit=128,
        ),
        chart_symbol=_safe_text(
            chart_summary_for_handoff.get("symbol")
            or chart_summary_for_handoff.get("ts_code")
            or chart_summary_for_handoff.get("confirmed_symbol")
            or chart_payload_for_handoff.get("symbol")
            or chart_payload_for_handoff.get("ts_code")
            or chart_payload_for_handoff.get("confirmed_symbol")
            or packet.get("symbol")
            or packet.get("ts_code")
            or "",
            limit=32,
        ),
    )
    candidate_radar_p3_ready = candidate_radar_p3_handoff.get("p3_readable_result_ready") is True
    candidate_radar_p2_ready = candidate_radar_p3_handoff.get("p2_small_data_ready") is True
    candidate_radar_handoff_ready = candidate_radar_p3_ready or candidate_radar_p2_ready
    if candidate_radar_p3_handoff:
        packet["candidate_radar_p3_handoff"] = candidate_radar_p3_handoff
        packet["latest_confirmed_symbol"] = candidate_radar_p3_handoff["symbol"]
        packet["latest_confirmed_symbol_source"] = "candidate_radar_p3_handoff"
        packet["latest_confirmed_task_id"] = candidate_radar_p3_handoff["source_task_id"]
        packet["latest_confirmed_task_status"] = candidate_radar_p3_handoff["source_task_status"]
        packet["latest_confirmed_task_current_step"] = candidate_radar_p3_handoff["source_task_current_step"]
        packet["result_version"] = candidate_radar_p3_handoff.get("result_version") or packet.get("result_version") or ""
        packet["current_result_task_id"] = (
            candidate_radar_p3_handoff.get("current_result_task_id") or packet.get("current_result_task_id") or ""
        )
        packet["chart_is_bound_to_current_result"] = (
            candidate_radar_p3_handoff.get("chart_is_bound_to_current_result") is True
        )
        packet["latest_confirmed_symbol_readback_external_calls_triggered"] = False
        packet["latest_confirmed_symbol_creates_task_from_readback"] = False
    if packet.get("status") == "cache_missing" and candidate_radar_handoff_ready:
        packet["status"] = "candidate_readable_result_replay_chart_pending"
        packet["cache_source"] = "candidate_radar_p3_handoff_readonly"
        packet["summary"] = (
            "上游搜票量化推演已有 Tushare-first 可读结果；完整次日图谱仍需手动生成本地 cache。"
        )
        packet["manual_required_text"] = (
            "可先读上游结论；点击本页生成任务才会写 next-session 图谱 cache，GET cache 不补调 provider/model。"
        )
        packet["chart_payload_generated"] = False
        packet["operation_zones_generated"] = False
        packet["manual_next_session_generate_required"] = True
    # A v0.5 local candidate task is the newest same-packet lineage.  Apply this
    # after the compatibility P3 handoff above so an older quant result summary
    # cannot reintroduce mixed result/date/freshness fields.
    packet = _apply_candidate_radar_v05_lineage(packet)
    retained_signal_capability_coverage = _next_session_same_packet_signal_capability_coverage(packet)
    packet["next_session_same_packet_signal_capability_coverage"] = retained_signal_capability_coverage
    packet["next_session_same_packet_signal_capability_coverage_rows"] = retained_signal_capability_coverage["rows"]
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
    persisted_streamlit_parity_review_packet = _read_next_session_streamlit_parity_review_packet()
    persisted_streamlit_parity_review = _as_dict(
        persisted_streamlit_parity_review_packet.get("next_session_streamlit_parity_review_contract")
    )
    persisted_promotion_review_packet = _read_next_session_production_promotion_review_packet()
    persisted_promotion_review = _as_dict(
        persisted_promotion_review_packet.get("next_session_production_promotion_review_contract")
    )
    existing_browser_qa_review = _as_dict(packet.get("next_session_browser_qa_review_contract"))
    if persisted_browser_qa_review.get("explicit_review_task_done") is True:
        browser_qa_review = persisted_browser_qa_review
    elif existing_browser_qa_review.get("explicit_review_task_done") is True:
        browser_qa_review = existing_browser_qa_review
    else:
        browser_qa_review = _next_session_browser_qa_review_contract(browser_qa_evidence, browser_qa_evidence_rows)
    existing_streamlit_parity_review = _as_dict(packet.get("next_session_streamlit_parity_review_contract"))
    if persisted_streamlit_parity_review.get("explicit_review_task_done") is True:
        streamlit_parity_review = persisted_streamlit_parity_review
    elif existing_streamlit_parity_review.get("explicit_review_task_done") is True:
        streamlit_parity_review = existing_streamlit_parity_review
    else:
        streamlit_parity_review = _next_session_streamlit_parity_review_contract(
            legacy_parity_recipe,
            legacy_parity_rows,
            retained_coverage=retained_signal_capability_coverage,
        )
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
    packet["next_session_streamlit_parity_review_contract"] = streamlit_parity_review
    packet["next_session_streamlit_parity_review_rows"] = _as_list(streamlit_parity_review.get("rows"))
    durable_evidence_recipe = _next_session_durable_evidence_recipe(packet, _now_iso())
    packet["next_session_durable_evidence_recipe"] = durable_evidence_recipe
    packet["next_session_durable_evidence_rows"] = durable_evidence_recipe["rows"]
    existing_promotion_review = _as_dict(packet.get("next_session_production_promotion_review_contract"))
    if persisted_promotion_review.get("explicit_review_task_done") is True:
        promotion_review = persisted_promotion_review
    elif existing_promotion_review.get("explicit_review_task_done") is True:
        promotion_review = existing_promotion_review
    else:
        promotion_review = _next_session_production_promotion_review_contract(packet)
    packet["next_session_production_promotion_review_contract"] = promotion_review
    packet["next_session_production_promotion_review_rows"] = _as_list(promotion_review.get("rows"))
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
    packet["next_session_streamlit_parity_review_ready"] = streamlit_parity_review[
        "local_streamlit_parity_review_ready"
    ]
    packet["next_session_streamlit_parity_review_blocking_count"] = streamlit_parity_review[
        "blocking_review_count"
    ]
    packet["next_session_durable_evidence_recipe_ready"] = durable_evidence_recipe["local_recipe_ready"]
    packet["next_session_durable_evidence_blocker_count"] = durable_evidence_recipe["durable_evidence_blocker_count"]
    packet["next_session_production_promotion_review_ready"] = promotion_review[
        "local_production_promotion_review_ready"
    ]
    packet["next_session_production_promotion_review_blocking_count"] = promotion_review[
        "blocking_review_count"
    ]
    packet["next_session_production_stage_scope_ready"] = production_stage_scope["local_manifest_ready"]
    packet["next_session_production_stage_scope_direct_evidence_count"] = production_stage_scope[
        "direct_evidence_stage_count"
    ]
    packet["next_session_production_stage_scope_pending_count"] = production_stage_scope["pending_stage_count"]
    packet["next_session_production_stage_scope_blocker_count"] = production_stage_scope["production_blocker_count"]
    ordinary_result_replay = _next_session_ordinary_result_replay(packet)
    ordinary_next_session_preview_rows = [
        {
            "预览项": str(row.get("surface") or row.get("step") or "次日图谱预览"),
            "当前状态": str(row.get("readable_result") or "等待本地回放"),
            "用户下一步": str(row.get("next_step") or "继续只读查看本地结果"),
            "证据": str(row.get("evidence") or "ordinary_result_replay_rows"),
            "边界": str(row.get("boundary") or "只读本地 cache；不创建 task、不调用 provider/model、不生成交易动作"),
            "readback_source": "ordinary_result_replay_rows",
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "calls_provider_or_model": False,
            "is_trade_signal": False,
            "contains_secret": False,
            **_local_ledger_boundary(),
        }
        for row in _as_list(ordinary_result_replay.get("result_rows"))
        if isinstance(row, dict)
    ]
    packet["ordinary_result_replay_summary"] = ordinary_result_replay
    packet["ordinary_result_replay_status"] = ordinary_result_replay["status"]
    if ordinary_result_replay["chart_ready_for_confirmed_symbol"]:
        packet["status"] = "ready_cache_replay"
        packet["cache_source"] = packet.get("cache_source") or "next_session_cache_readonly"
        packet["chart_payload_generated"] = True
        packet["operation_zones_generated"] = True
        packet["manual_next_session_generate_required"] = False
    elif ordinary_result_replay["status"] == "candidate_readable_result_replay_chart_pending":
        packet["status"] = "candidate_readable_result_replay_chart_pending"
        packet["cache_source"] = "candidate_radar_p3_handoff_readonly"
        packet["summary"] = (
            "上游搜票量化推演已有 Tushare-first 可读结果；完整次日图谱仍需手动生成本地 cache。"
        )
        packet["manual_required_text"] = (
            "可先读上游结论；点击本页生成任务才会写 next-session 图谱 cache，GET cache 不补调 provider/model。"
        )
        packet["chart_payload_generated"] = False
        packet["operation_zones_generated"] = False
        packet["manual_next_session_generate_required"] = True
    packet["ordinary_result_replay_rows"] = ordinary_result_replay["result_rows"]
    packet["ordinary_next_session_preview_rows"] = ordinary_next_session_preview_rows
    packet["ordinary_next_session_preview_row_count"] = len(ordinary_next_session_preview_rows)
    packet["ordinary_summary"] = (
        "次日图谱已可读：路径、参考线和操作区来自本地 cache。"
        if ordinary_result_replay["chart_ready_for_confirmed_symbol"]
        else "上游确认结果已接上；完整次日图谱待手动生成，本页只读展示预览和边界。"
        if ordinary_result_replay["status"] == "candidate_readable_result_replay_chart_pending"
        else "等待确认标的或本地图谱 cache。"
    )
    packet["ordinary_chart_review_rows"] = ordinary_result_replay["chart_review_rows"]
    packet["ordinary_condition_quick_read_rows"] = ordinary_result_replay["condition_quick_read_rows"]
    counts = _as_dict(packet.get("counts"))
    counts.update(
        {
            "next_session_production_stage_scope_count": production_stage_scope["stage_count"],
            "next_session_production_stage_scope_direct_evidence_count": production_stage_scope[
                "direct_evidence_stage_count"
            ],
            "next_session_production_stage_scope_pending_count": production_stage_scope["pending_stage_count"],
            "next_session_production_stage_scope_blocker_count": production_stage_scope["production_blocker_count"],
            "next_session_streamlit_parity_review_ready": streamlit_parity_review[
                "local_streamlit_parity_review_ready"
            ],
            "next_session_streamlit_parity_review_blocking_count": streamlit_parity_review[
                "blocking_review_count"
            ],
            "next_session_production_promotion_review_ready": promotion_review[
                "local_production_promotion_review_ready"
            ],
            "next_session_production_promotion_review_blocking_count": promotion_review[
                "blocking_review_count"
            ],
            "next_session_ordinary_result_replay_row_count": ordinary_result_replay["row_count"],
            "next_session_ordinary_preview_row_count": len(ordinary_next_session_preview_rows),
            "next_session_ordinary_chart_review_row_count": ordinary_result_replay["chart_review_row_count"],
            "next_session_ordinary_condition_quick_read_row_count": ordinary_result_replay[
                "condition_quick_read_row_count"
            ],
            "next_session_candidate_radar_p3_handoff_ready": candidate_radar_p3_ready,
            "next_session_candidate_radar_p2_handoff_ready": candidate_radar_p2_ready,
            "next_session_latest_confirmed_readback_ready": bool(candidate_radar_p3_handoff),
            "next_session_chart_has_drawable_data": ordinary_result_replay["chart_has_drawable_data"],
            "next_session_chart_ready_for_confirmed_symbol": ordinary_result_replay[
                "chart_ready_for_confirmed_symbol"
            ],
            "next_session_chart_stale_for_confirmed_symbol": ordinary_result_replay[
                "chart_stale_for_confirmed_symbol"
            ],
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
            "next_session_streamlit_parity_review_is_button_gated": True,
            "next_session_streamlit_parity_review_opens_no_streamlit": True,
            "next_session_streamlit_parity_review_is_not_production_completion": True,
            "next_session_production_promotion_review_is_button_gated": True,
            "next_session_production_promotion_review_is_not_production_completion": True,
            "next_session_production_promotion_review_calls_no_provider_model_or_github": True,
            "next_session_ordinary_result_replay_rows_are_cache_only": True,
            "next_session_ordinary_result_replay_rows_create_task": False,
            "next_session_ordinary_result_replay_rows_call_provider_or_model": False,
            "next_session_ordinary_result_replay_rows_are_not_trade_signals": True,
            "ordinary_next_session_preview_rows_are_cache_only": True,
            "ordinary_next_session_preview_rows_create_task": False,
            "ordinary_next_session_preview_rows_call_provider_or_model": False,
            "ordinary_next_session_preview_rows_are_not_trade_signals": True,
            "next_session_ordinary_condition_quick_read_rows_are_cache_only": True,
            "next_session_ordinary_condition_quick_read_rows_call_provider_or_model": False,
            "next_session_ordinary_condition_quick_read_rows_are_not_trade_signals": True,
            "next_session_candidate_radar_p3_handoff_is_cache_only": True,
            "next_session_candidate_radar_p3_handoff_creates_task": False,
            "next_session_candidate_radar_p3_handoff_calls_provider_or_model": False,
            "next_session_candidate_radar_p3_handoff_is_not_trade_signal": True,
            "next_session_latest_confirmed_readback_is_cache_only": True,
            "next_session_latest_confirmed_readback_creates_task": False,
            "next_session_latest_confirmed_readback_calls_provider_or_model": False,
            "next_session_latest_confirmed_readback_is_not_trade_signal": True,
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
    streamlit_review_ledger = [
        row
        for row in _as_list(persisted_streamlit_parity_review_packet.get("call_ledger"))
        if isinstance(row, dict)
    ]
    if streamlit_review_ledger:
        existing_ledger.extend(streamlit_review_ledger)
    promotion_review_ledger = [
        row for row in _as_list(persisted_promotion_review_packet.get("call_ledger")) if isinstance(row, dict)
    ]
    if promotion_review_ledger:
        existing_ledger.extend(promotion_review_ledger)
    candidate_handoff_ledger = [
        row for row in _as_list(candidate_radar_p3_handoff.get("call_ledger")) if isinstance(row, dict)
    ]
    if candidate_handoff_ledger:
        existing_ledger.extend(candidate_handoff_ledger)
    packet["call_ledger"] = (
        existing_ledger + durable_evidence_recipe["call_ledger"] + production_stage_scope["call_ledger"]
    )
    packet.setdefault("cache_only", True)
    packet.setdefault("read_only", True)
    packet["external_calls_triggered"] = False
    packet["tushare_called"] = False
    packet["deepseek_called"] = False
    packet["github_called"] = False
    packet["provider_or_model_calls"] = False
    packet.setdefault("contains_secret", False)
    packet.setdefault("does_not_execute_trades", True)
    packet.setdefault("does_not_modify_action", True)
    packet.setdefault("does_not_modify_strategy_action", True)
    packet.setdefault("does_not_modify_operation_zones", True)
    warnings = [str(item) for item in _as_list(packet.get("warnings"))]
    for warning in [
        "GET /api/next-session/cache 只读取本地次日图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
        " next_session_replacement_activation_receipt 只是替代验收路径，不运行浏览器、不证明生产替代完成。",
        "next_session_streamlit_parity_review 只审查本地同包 no-feature-loss 证据；不会打开 Streamlit、不会运行浏览器、不会移除 fallback、不会证明生产替代完成。",
        "next_session_durable_evidence_recipe 只固定 ECharts 生产替代前的 durable evidence 清单；不会打开浏览器、调用 provider/model、执行交易或证明生产替代完成。",
        "next_session_production_promotion_review 只审查本地 promotion 阻断状态；不会调用 provider/model/GitHub、不会移除 fallback、不会证明生产替代完成。",
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
            "review 结果只代表本地 artifact 审查状态；不代表 legacy signal/capability parity、durable CI evidence 或 production ECharts replacement。",
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


def _next_session_streamlit_parity_review_call_ledger(review_contract: Mapping[str, Any], now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_next_session_streamlit_parity_review",
            "request_params_safe": {
                "review_scope": "next_session_same_packet_no_feature_loss",
                "next_route": "#next",
                "external_sources_allowed": False,
                "opens_no_streamlit": True,
                "opens_no_browser": True,
                "writes_no_artifacts": True,
                "streamlit_parity_complete": False,
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


def run_next_session_streamlit_parity_review_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_next_session_streamlit_parity_review",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_streamlit_parity_review_queued",
        warnings=[
            "次日图谱 legacy signal/capability parity review 只审查当前本地同包 no-feature-loss 合同；不会打开 Streamlit、浏览器或启动服务。",
            "review 结果不代表 Streamlit reference capture、durable CI evidence、fallback removal 或 production ECharts replacement。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_next_session_same_packet_parity_contract",
    )
    packet = read_next_session_cache()
    parity_recipe = _as_dict(packet.get("next_session_legacy_parity_execution_recipe"))
    parity_rows = [row for row in _as_list(packet.get("next_session_legacy_parity_execution_rows")) if isinstance(row, dict)]
    retained_coverage = _as_dict(packet.get("next_session_same_packet_signal_capability_coverage"))
    reviewed_at = _now_iso()
    review_contract = _next_session_streamlit_parity_review_contract(
        parity_recipe,
        parity_rows,
        explicit_review=True,
        task_id=task["task_id"],
        reviewed_at=reviewed_at,
        retained_coverage=retained_coverage,
    )
    ledger = _next_session_streamlit_parity_review_call_ledger(review_contract, reviewed_at)
    _write_next_session_streamlit_parity_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    refreshed = read_next_session_cache()
    refreshed["task_id"] = task["task_id"]
    refreshed["next_session_streamlit_parity_review_completed_at"] = reviewed_at
    refreshed["task_call_ledger"] = ledger
    if _persistable_next_session_packet(refreshed):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_next_session_projection_packet", refreshed)
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="next_session_streamlit_parity_review_ready"
        if review_contract["local_streamlit_parity_review_ready"]
        else "next_session_streamlit_parity_review_pending",
        call_ledger=ledger,
        warning="next_session_streamlit_parity_review_completed_no_external_call",
    ) or task


def _next_session_production_promotion_review_call_ledger(
    review_contract: Mapping[str, Any], now: str
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_next_session_production_promotion_review",
            "request_params_safe": {
                "review_scope": "next_session_local_promotion_blocker_review",
                "next_route": "#next",
                "external_sources_allowed": False,
                "opens_no_streamlit": True,
                "opens_no_browser": True,
                "writes_no_artifacts": True,
                "ready_to_mark_production_replacement_complete": False,
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


def run_next_session_production_promotion_review_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_next_session_production_promotion_review",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_production_promotion_review_queued",
        warnings=[
            "次日图谱 production promotion review 只审查本地证据和阻断状态；不会打开 Streamlit、浏览器或启动服务。",
            "review 结果不代表 durable CI/release evidence、fallback removal 或 production ECharts replacement。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_next_session_local_promotion_evidence",
    )
    packet = read_next_session_cache()
    reviewed_at = _now_iso()
    review_contract = _next_session_production_promotion_review_contract(
        packet,
        explicit_review=True,
        task_id=task["task_id"],
        reviewed_at=reviewed_at,
    )
    ledger = _next_session_production_promotion_review_call_ledger(review_contract, reviewed_at)
    _write_next_session_production_promotion_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    refreshed = read_next_session_cache()
    refreshed["task_id"] = task["task_id"]
    refreshed["next_session_production_promotion_review_completed_at"] = reviewed_at
    refreshed["task_call_ledger"] = ledger
    if _persistable_next_session_packet(refreshed):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_next_session_projection_packet", refreshed)
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="next_session_production_promotion_review_ready"
        if review_contract["local_production_promotion_review_ready"]
        else "next_session_production_promotion_review_pending",
        call_ledger=ledger,
        warning="next_session_production_promotion_review_completed_no_external_call",
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


def _read_candidate_radar_p3_handoff(
    *,
    chart_source_task_id: str = "",
    chart_result_version: str = "",
    chart_symbol: str = "",
) -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {}
    try:
        candidate_packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(CANDIDATE_RADAR_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(candidate_packet, Mapping):
        return {}
    small_data = _as_dict(candidate_packet.get("search_quant_projection_small_data_writeback_summary"))
    interpretation = _as_dict(candidate_packet.get("search_quant_projection_interpretation_summary"))
    receipt = _as_dict(candidate_packet.get("search_quant_projection_receipt"))
    provider_receipt = _as_dict(candidate_packet.get("search_quant_provider_model_acceptance_receipt"))
    result_lineage = _as_dict(candidate_packet.get("search_quant_result_lineage"))
    result_version_summary = _as_dict(candidate_packet.get("search_quant_result_version_summary"))
    p2_ready = small_data.get("small_data_writeback_ready") is True
    interpretation_uses_model_output = any(
        interpretation.get(key) is True
        for key in ("uses_model_output", "uses_deepseek_output", "model_output_used")
    )
    p3_ready = not interpretation_uses_model_output and (
        interpretation.get("interpretation_ready") is True
        or bool(
            str(
                interpretation.get("ordinary_result_summary")
                or candidate_packet.get("ordinary_result_summary")
                or ""
            ).strip()
        )
    )
    if not (p2_ready or p3_ready):
        return {}
    if (
        candidate_packet.get("contains_secret") is True
        or interpretation.get("contains_secret") is True
        or small_data.get("contains_secret") is True
    ):
        return {}
    symbol = _safe_text(
        candidate_packet.get("latest_confirmed_symbol")
        or receipt.get("symbol")
        or small_data.get("symbol")
        or interpretation.get("symbol")
        or "",
        limit=32,
    )
    latest_confirmed_task_id = _safe_text(candidate_packet.get("latest_confirmed_task_id") or "", limit=128)
    current_result_task_id = _safe_text(
        result_version_summary.get("current_result_task_id")
        or result_version_summary.get("canonical_result_task_id")
        or result_lineage.get("task_id")
        or provider_receipt.get("task_id")
        or "",
        limit=128,
    )
    current_result_version = _safe_text(
        result_version_summary.get("current_result_version")
        or result_version_summary.get("canonical_result_version")
        or result_lineage.get("result_version")
        or provider_receipt.get("result_version")
        or "",
        limit=128,
    )
    chart_source_task_id_safe = _safe_text(chart_source_task_id or "", limit=128)
    chart_result_version_safe = _safe_text(chart_result_version or "", limit=128)
    chart_symbol_safe = _safe_text(chart_symbol or "", limit=32).upper()
    symbol_matches_chart = bool(not chart_symbol_safe or not symbol or chart_symbol_safe == symbol.upper())
    chart_matches_latest_confirmed_task = bool(
        chart_source_task_id_safe
        and latest_confirmed_task_id
        and chart_source_task_id_safe == latest_confirmed_task_id
        and symbol_matches_chart
    )
    chart_matches_current_result_task = bool(
        chart_source_task_id_safe
        and current_result_task_id
        and chart_source_task_id_safe == current_result_task_id
        and symbol_matches_chart
    )
    chart_matches_current_result_version = bool(
        chart_result_version_safe
        and current_result_version
        and chart_result_version_safe == current_result_version
        and symbol_matches_chart
    )
    chart_is_bound_to_current_result = bool(
        chart_matches_current_result_task or chart_matches_current_result_version
    )
    chart_is_bound_to_latest_confirmed = bool(
        chart_matches_latest_confirmed_task or chart_is_bound_to_current_result
    )
    source_task_id = _safe_text(
        current_result_task_id
        if chart_is_bound_to_current_result
        else latest_confirmed_task_id
        if chart_matches_latest_confirmed_task
        else (
            current_result_task_id
            or result_version_summary.get("latest_task_id")
            or result_lineage.get("task_id")
            or provider_receipt.get("task_id")
            or latest_confirmed_task_id
            or receipt.get("latest_task_id")
            or receipt.get("task_id")
            or small_data.get("latest_task_id")
            or candidate_packet.get("task_id")
            or ""
        ),
        limit=128,
    )
    source_task_status = _safe_text(
        candidate_packet.get("latest_confirmed_task_status")
        or candidate_packet.get("latest_task_status")
        or receipt.get("latest_task_status")
        or "",
        limit=48,
    )
    source_task_current_step = _safe_text(
        candidate_packet.get("latest_confirmed_task_current_step")
        or candidate_packet.get("latest_task_current_step")
        or receipt.get("latest_task_current_step")
        or "",
        limit=160,
    )
    if p3_ready:
        result_summary_raw = (
            interpretation.get("ordinary_result_summary")
            or candidate_packet.get("ordinary_result_summary")
            or small_data.get("ordinary_readback_summary")
            or small_data.get("summary_label")
            or "上游 Tushare-first 结果可读；完整次日图谱待手动生成。"
        )
        result_next_step_raw = (
            interpretation.get("ordinary_result_next_step")
            or candidate_packet.get("ordinary_result_next_step")
            or small_data.get("ordinary_readback_next_step")
            or "可在本页手动生成完整次日图谱；GET cache 不会补调 provider/model。"
        )
        result_boundary_raw = (
            interpretation.get("ordinary_result_boundary")
            or candidate_packet.get("ordinary_result_boundary")
            or "只读回放 CandidateRadar cache / ledger / packet；不创建 task、不调用 Tushare/DeepSeek、不改 operation_zones 或 strategy action。"
        )
        interpretation_rows = _as_list(interpretation.get("ordinary_result_quick_read_rows"))
        deepseek_governed_executor_status = (
            interpretation.get("deepseek_governed_executor_status")
            or candidate_packet.get("ordinary_result_deepseek_governed_executor_status")
            or "skipped_or_pending_governed_executor"
        )
    else:
        result_summary_raw = (
            small_data.get("ordinary_readback_summary")
            or small_data.get("summary_label")
            or "上游 Tushare-first 小数据账本已可读；DeepSeek 解释不作为次日图谱依据。"
        )
        result_next_step_raw = (
            small_data.get("ordinary_readback_next_step")
            or "可在本页手动生成完整次日图谱；GET cache 不会补调 provider/model。"
        )
        result_boundary_raw = (
            small_data.get("ordinary_result_boundary")
            or "只读回放 CandidateRadar 的 Tushare 小数据账本；DeepSeek 解释不用于价格、区间或 strategy action。"
        )
        interpretation_rows = []
        deepseek_governed_executor_status = (
            "model_output_ignored_for_next_session_handoff"
            if interpretation_uses_model_output
            else "skipped_or_pending_governed_executor"
        )
    provider_success_count = int(small_data.get("provider_api_success_count") or 0)
    provider_call_count = int(small_data.get("provider_api_call_count") or 0)
    provider_call_source = _safe_text(small_data.get("provider_call_source") or "candidate_radar_cache")
    source_task_external_calls_triggered = (
        small_data.get("source_task_external_calls_triggered") is True
        or (provider_call_source == "post_task_call_ledger" and provider_success_count > 0)
    )
    source_task_tushare_called = (
        small_data.get("source_task_tushare_called") is True
        or source_task_external_calls_triggered
    )
    source_task_tushare_provider_ledger_ready = (
        small_data.get("source_task_tushare_provider_ledger_ready") is True
        or bool(p2_ready and provider_success_count > 0)
    )
    result_summary = _source_task_readback_text(
        result_summary_raw,
        source_task_tushare_called=source_task_tushare_called,
        limit=360,
    )
    result_next_step = _safe_text(
        result_next_step_raw,
        limit=300,
    )
    result_boundary = _safe_text(
        result_boundary_raw,
        limit=360,
    )
    ordinary_readback_provenance_summary = _safe_text(
        small_data.get("ordinary_readback_provenance_summary")
        or "当前读回来自 GET cache 的本地 packet；provider 证据只由 POST task call_ledger 证明，React render 不补调 provider/model。",
        limit=360,
    )
    status = "candidate_readable_result_ready_chart_pending" if p3_ready else "candidate_small_data_ready_chart_pending"
    ledger = {
        "api": "local_next_session_candidate_radar_p3_handoff",
        "request_params_safe": {
            "source_packet_key": CANDIDATE_RADAR_PACKET_KEY,
            "source_task_id": source_task_id,
            "latest_confirmed_task_id": latest_confirmed_task_id,
            "current_result_task_id": current_result_task_id,
            "chart_source_task_id": chart_source_task_id_safe,
            "result_version": current_result_version,
            "chart_result_version": chart_result_version_safe,
            "chart_is_bound_to_latest_confirmed": chart_is_bound_to_latest_confirmed,
            "chart_is_bound_to_current_result": chart_is_bound_to_current_result,
            "symbol": symbol,
            "p2_small_data_ready": p2_ready,
            "p3_readable_result_ready": p3_ready,
            "provider_api_success_count": provider_success_count,
            "provider_api_call_count": provider_call_count,
            "source_task_tushare_called": source_task_tushare_called,
            "p3_model_output_ignored_for_chart": interpretation_uses_model_output,
            "readback_tushare_called": False,
            "does_not_include_token_or_raw_log": True,
        },
        "row_count": len(interpretation_rows),
        "data_date": small_data.get("data_date") or candidate_packet.get("trade_date"),
        "local_fetched_at": _now_iso(),
        "call_status": status,
        "error_message_safe": "",
        **_local_ledger_boundary(),
    }
    return {
        "schema_version": "next_session_candidate_radar_p3_handoff.v1",
        "status": status,
        "source_packet_key": CANDIDATE_RADAR_PACKET_KEY,
        "source_task_id": source_task_id,
        "latest_confirmed_task_id": latest_confirmed_task_id,
        "current_result_task_id": current_result_task_id,
        "chart_source_task_id": chart_source_task_id_safe,
        "result_version": current_result_version,
        "chart_result_version": chart_result_version_safe,
        "chart_is_bound_to_latest_confirmed": chart_is_bound_to_latest_confirmed,
        "chart_is_bound_to_current_result": chart_is_bound_to_current_result,
        "source_task_status": source_task_status,
        "source_task_current_step": source_task_current_step,
        "symbol": symbol,
        "p2_small_data_ready": p2_ready,
        "p3_readable_result_ready": p3_ready,
        "ordinary_result_summary": result_summary,
        "ordinary_result_next_step": result_next_step,
        "ordinary_result_boundary": result_boundary,
        "provider_api_success_count": provider_success_count,
        "provider_api_call_count": provider_call_count,
        "provider_call_source": provider_call_source,
        "provider_call_ledger_replayed_from_source_task": source_task_tushare_provider_ledger_ready,
        "source_task_external_calls_triggered": source_task_external_calls_triggered,
        "source_task_tushare_called": source_task_tushare_called,
        "source_task_tushare_provider_ledger_ready": source_task_tushare_provider_ledger_ready,
        "p3_model_output_ignored_for_chart": interpretation_uses_model_output,
        "p2_tushare_handoff_used_without_deepseek_output": bool(p2_ready and interpretation_uses_model_output),
        "readback_external_calls_triggered": False,
        "readback_tushare_called": False,
        "ordinary_readback_provenance_summary": ordinary_readback_provenance_summary,
        "deepseek_governed_executor_status": deepseek_governed_executor_status,
        "chart_payload_generated": False,
        "operation_zones_generated": False,
        "manual_next_session_generate_required": True,
        "cache_only_readback": True,
        "creates_task_from_readback": False,
        "calls_provider_or_model": False,
        "uses_model_output": False,
        "uses_deepseek_output": False,
        "contains_secret": False,
        "candidate_is_not_buy_instruction": True,
        "call_ledger": [ledger],
        **_local_ledger_boundary(),
    }


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


def _local_exact_next_session_sample_packet(
    now: str,
    *,
    symbol: str = "",
    source_task_id: str = "",
) -> dict[str, Any]:
    symbol_safe = _safe_text(symbol, limit=32).upper()
    source_task_id_safe = _safe_text(source_task_id, limit=128)
    chart_payload = {
        "status": "ready",
        "source_packet": "command_center_next_session_projection_packet",
        "symbol": symbol_safe,
        "ts_code": symbol_safe,
        "confirmed_symbol": symbol_safe,
        "source_task_id": source_task_id_safe,
        "is_exact_next_session_packet": True,
        "uses_real_daily_close": False,
        "historical_source_label": "button_gated_local_preview_no_provider",
        "future_source_label": "button_gated_local_preview_scenarios",
        "historical_points": [
            {"x": "2026-06-08", "price": 10.0, "source": "button_gated_local_preview"},
            {"x": "2026-06-09", "price": 10.4, "source": "button_gated_local_preview"},
        ],
        "scenario_series": [
            {
                "scenario_key": "neutral",
                "scenario_name": "中性路径",
                "trigger_condition": "放量但不追高",
                "risk_note": "本地预览只用于复核图谱结构，不能替代 provider-backed daily close。",
                "points": [
                    {"x": "T0", "price": 10.4, "source": "button_gated_local_preview"},
                    {"x": "T+1_close", "price": 10.8, "source": "button_gated_local_preview"},
                ],
            }
        ],
        "reference_lines": [
            {"key": "current", "label": "当前价参考", "value": 10.4, "tone": "blue"},
            {"key": "support", "label": "支撑参考", "value": 9.9, "tone": "green"},
            {"key": "resistance", "label": "压力参考", "value": 11.0, "tone": "red"},
        ],
        "operation_zones": [
            {
                "zone_key": "reduce_watch_zone",
                "zone_name": "止盈/减仓观察区",
                "price_range": [10.9, 11.3],
                "action_mode": "condition_only",
                "guardrail": "只读条件区间，不生成买卖指令、不改 operation_zones。",
            }
        ],
        "y_axis_range": [9.0, 12.0],
        "deepseek_status": "not_called",
        "position_conflict": {
            "status": "local_preview_conflict_visible",
            "conflict_flags": ["cost_price_conflict"],
            "source_packet": "button_gated_local_preview_position_context",
        },
        "data_trust_summary": {
            "facts": [{"fact_key": "moneyflow", "call_status": "local_preview_not_provider_verified"}],
            "human_summary": ["按钮门控本地预览：不代表真实 provider 验收", "持仓冲突展示：仅验证可视化边界"],
            "deepseek": {"label": "DeepSeek", "status": "not_called"},
        },
        "warnings": [
            "按钮门控本地预览用于让当前确认标的先有可读图谱；不是 provider-backed market data。",
            "GET cache 和 React render 不会生成该预览；只有 POST /api/next-session/generate 可写入。",
        ],
    }
    return {
        "packet_key": "command_center_next_session_projection_packet",
        "schema_version": "next_session_projection.v1",
        "status": "ready",
        "source_type": "button_gated_local_confirmed_symbol_preview",
        "cache_source": "button_gated_local_preview_no_provider",
        "symbol": symbol_safe,
        "ts_code": symbol_safe,
        "confirmed_symbol": symbol_safe,
        "source_task_id": source_task_id_safe,
        "trade_date": "20260610",
        "generated_at": now,
        "chart_payload": chart_payload,
        "chart_render_model": {
            "historical_series": [
                {"x": "2026-06-08", "price": 10.0, "source": "button_gated_local_preview"},
                {"x": "2026-06-09", "close": 10.4, "source": "button_gated_local_preview"},
            ],
            "scenario_series": [
                {
                    "scenario_key": "neutral",
                    "scenario_name": "中性路径",
                    "trigger_condition": "放量但不追高",
                    "confidence_note": "本地预览只用于复核图谱结构",
                    "points": [
                        {"x": "T0", "price": 10.4},
                        {"x": "T+1_close", "price": 10.8},
                    ],
                }
            ],
            "cost_line": 9.8,
            "current_price_line": 10.4,
            "limit_lines": [
                {"label": "涨停参考", "value": 11.44},
                {"label": "跌停参考", "value": 9.36},
            ],
            "support_lines": [9.9],
            "resistance_lines": [11.0],
            "operation_zone_overlays": [
                {
                    "zone_key": "reduce_watch_zone",
                    "zone_name": "止盈/减仓观察区",
                    "price_range": [10.9, 11.3],
                    "action_mode": "condition_only",
                }
            ],
            "y_axis_range": [9.0, 12.0],
        },
        "position_context": {
            "conflict_flags": ["cost_price_conflict"],
            "source_packet": "button_gated_local_preview_position_context",
        },
        "data_trust_summary": {
            "facts": [{"fact_key": "moneyflow", "call_status": "local_preview_not_provider_verified"}],
            "human_summary": ["按钮门控本地预览：不代表真实 provider 验收", "持仓冲突展示：仅验证可视化边界"],
            "deepseek": {"label": "DeepSeek", "status": "not_called"},
        },
        "deepseek_synthesis": {"status": "not_called"},
        "local_exact_sample_for_same_packet_parity": False,
        "button_gated_local_confirmed_symbol_preview": True,
        "provider_backed": False,
        "production_replacement_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_action": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
        "warnings": [
            "This is a button-gated local confirmed-symbol preview for ordinary Next Session readability.",
            "It is not provider-backed market data, Streamlit reference capture, browser QA, durable CI evidence, or production ECharts replacement.",
        ],
    }


def _apply_candidate_radar_v05_lineage(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep the v0.5 local candidate handoff authoritative on the Next Session surface.

    CandidateRadar still carries older P2/P3 result summaries for compatibility.  Those
    summaries must not overwrite the newer v0.5 same-packet lineage, otherwise the UI can
    show a stale result_version/data date/freshness next to the current candidate task.
    This is a readback normalization only; it never calls a provider or writes cache.
    """
    lineage = _as_dict(packet.get("candidate_radar_v05_lineage"))
    if lineage.get("status") != "same_packet_lineage_ready":
        return packet
    result_version = _safe_text(lineage.get("candidate_result_version") or "", limit=128)
    task_id = _safe_text(lineage.get("candidate_task_id") or "", limit=128)
    symbol = _safe_text(lineage.get("symbol") or "", limit=32)
    data_date = lineage.get("data_date")
    freshness_state = _as_dict(lineage.get("freshness_state"))
    if not (result_version and task_id and symbol and data_date and freshness_state):
        return packet
    normalized = dict(packet)
    normalized["result_version"] = result_version
    normalized["current_result_task_id"] = task_id
    normalized["source_task_id"] = task_id
    normalized["latest_confirmed_task_id"] = task_id
    normalized["latest_confirmed_symbol"] = symbol
    normalized["trade_date"] = data_date
    normalized["data_date"] = data_date
    normalized["freshness_state"] = dict(freshness_state)
    normalized["candidate_radar_v05_result_version"] = result_version
    normalized["candidate_radar_v05_source_task_id"] = task_id
    normalized["candidate_radar_v05_data_date"] = data_date
    normalized["candidate_radar_v05_freshness_state"] = dict(freshness_state)
    normalized["candidate_radar_v05_readback_authoritative"] = True
    # The compatibility P3 handoff can still point at an older searched symbol
    # and provider task.  Keep the handoff envelope itself on the same v0.5
    # lineage so the ordinary replay cannot mix old symbol/date/provider facts
    # with the current local Candidate Radar result.
    legacy_handoff = _as_dict(packet.get("candidate_radar_p3_handoff"))
    if legacy_handoff:
        handoff = dict(legacy_handoff)
        handoff.update(
            {
                "status": "candidate_radar_v05_local_batch_ready_chart_pending",
                "source_task_id": task_id,
                "latest_confirmed_task_id": task_id,
                "current_result_task_id": task_id,
                "chart_source_task_id": task_id,
                "result_version": result_version,
                "chart_result_version": result_version,
                "chart_is_bound_to_latest_confirmed": True,
                "chart_is_bound_to_current_result": True,
                "symbol": symbol,
                "p2_small_data_ready": True,
                "p3_readable_result_ready": True,
                "provider_api_success_count": 0,
                "provider_api_call_count": 0,
                "provider_call_source": "candidate_radar_v05_local_batch",
                "provider_call_ledger_replayed_from_source_task": False,
                "source_task_external_calls_triggered": False,
                "source_task_tushare_called": False,
                "source_task_tushare_provider_ledger_ready": False,
                "deepseek_governed_executor_status": "pending_disabled_not_called",
                "uses_model_output": False,
                "uses_deepseek_output": False,
                "chart_payload_generated": (
                    _as_dict(packet.get("chart_payload")).get("is_exact_next_session_packet") is True
                ),
                "operation_zones_generated": bool(
                    _as_dict(packet.get("chart_payload")).get("zone_interaction_rows")
                ),
                "manual_next_session_generate_required": (
                    _as_dict(packet.get("chart_payload")).get("is_exact_next_session_packet") is not True
                ),
                "cache_only_readback": True,
                "creates_task_from_readback": False,
                "calls_provider_or_model": False,
                "candidate_is_not_buy_instruction": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_operation_zones": True,
                "contains_secret": False,
            }
        )
        normalized["candidate_radar_p3_handoff"] = handoff
    return normalized


def create_next_session_task(payload: Any = None) -> dict[str, Any]:
    payload_dict = _as_dict(payload)
    requested_symbol = _safe_text(payload_dict.get("symbol") or payload_dict.get("ts_code") or "", limit=32).upper()
    source_task_id = _safe_text(payload_dict.get("source_task_id") or "", limit=128)
    local_exact_sample_allowed = payload_dict.get("local_exact_sample_allowed") is True
    local_confirmed_preview_requested = payload_dict.get("manual_button_required") is True and bool(requested_symbol)
    local_confirmed_preview_allowed = local_confirmed_preview_requested and (
        payload_dict.get("p2_small_data_ready") is True
        or payload_dict.get("p3_readable_result_ready") is True
    )
    task = create_task_record(
        "build_next_session_projection",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_cache_pipeline_queued",
        warnings=[
            "Command Center 3.0 当前只执行本地 cache pipeline；不调用 Tushare、DeepSeek、GitHub。",
            "任务读取并持久化已有次日图谱 packet；当前确认标的缺少可读图谱时，可写按钮门控本地预览，不修改 strategy action 或 operation_zones。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="reading_next_session_cache")
    now = _now_iso()
    try:
        packet = dict(read_next_session_cache())
        local_exact_sample_written = False
        local_confirmed_preview_written = False
        candidate_handoff = _as_dict(packet.get("candidate_radar_p3_handoff"))
        ordinary_replay = _as_dict(packet.get("ordinary_result_replay_summary"))
        cache_confirmed_symbol = _safe_text(
            candidate_handoff.get("symbol") or packet.get("latest_confirmed_symbol") or "",
            limit=32,
        ).upper()
        cache_candidate_preview_allowed = bool(
            local_confirmed_preview_requested
            and (not cache_confirmed_symbol or cache_confirmed_symbol == requested_symbol)
            and (
                candidate_handoff.get("p2_small_data_ready") is True
                or candidate_handoff.get("p3_readable_result_ready") is True
                or ordinary_replay.get("status") == "candidate_readable_result_replay_chart_pending"
                or packet.get("status") == "candidate_readable_result_replay_chart_pending"
            )
        )
        local_confirmed_preview_allowed = local_confirmed_preview_allowed or cache_candidate_preview_allowed
        chart_payload = _as_dict(packet.get("chart_payload"))
        chart_has_drawable_data = bool(
            _as_list(chart_payload.get("historical_points")) or _as_list(chart_payload.get("scenario_series"))
        )
        chart_symbol = _safe_text(
            chart_payload.get("symbol")
            or chart_payload.get("ts_code")
            or chart_payload.get("confirmed_symbol")
            or packet.get("symbol")
            or packet.get("ts_code")
            or packet.get("confirmed_symbol")
            or "",
            limit=32,
        ).upper()
        chart_source_task_id = _safe_text(
            chart_payload.get("source_task_id") or packet.get("source_task_id") or "",
            limit=128,
        )
        chart_source_task_ready = (
            True
            if not (local_confirmed_preview_requested and source_task_id)
            else chart_source_task_id == source_task_id
        )
        chart_ready_for_requested_symbol = bool(
            chart_has_drawable_data
            and (not requested_symbol or chart_symbol == requested_symbol)
            and chart_source_task_ready
        )
        if (
            packet.get("status") == "cache_missing" and local_exact_sample_allowed
        ) or (
            local_confirmed_preview_allowed and not chart_ready_for_requested_symbol
        ):
            SQLiteMetaStore(SQLITE_META_PATH).write_packet(
                "command_center_next_session_projection_packet",
                _local_exact_next_session_sample_packet(
                    now,
                    symbol=requested_symbol,
                    source_task_id=source_task_id,
                ),
            )
            local_exact_sample_written = True
            local_confirmed_preview_written = local_confirmed_preview_allowed
            packet = dict(read_next_session_cache())
            packet["local_exact_sample_for_same_packet_parity"] = not local_confirmed_preview_written
            packet["button_gated_local_confirmed_symbol_preview"] = local_confirmed_preview_written
            packet["provider_backed"] = False
        packet["task_call_ledger"] = _next_session_cache_call_ledger(packet, now)
        if local_exact_sample_written:
            packet["task_call_ledger"][0]["call_status"] = (
                "local_confirmed_symbol_preview_written"
                if local_confirmed_preview_written
                else "local_exact_sample_written"
            )
            packet["task_call_ledger"][0]["request_params_safe"]["local_exact_sample_allowed"] = (
                local_exact_sample_allowed
            )
            packet["task_call_ledger"][0]["request_params_safe"]["local_confirmed_preview_allowed"] = (
                local_confirmed_preview_allowed
            )
            packet["task_call_ledger"][0]["request_params_safe"]["cache_candidate_preview_allowed"] = (
                cache_candidate_preview_allowed
            )
            packet["task_call_ledger"][0]["request_params_safe"]["cache_confirmed_symbol"] = cache_confirmed_symbol
            packet["task_call_ledger"][0]["request_params_safe"]["symbol"] = requested_symbol
            packet["task_call_ledger"][0]["request_params_safe"]["source_task_id"] = source_task_id
            packet["task_call_ledger"][0]["request_params_safe"]["prior_chart_symbol"] = chart_symbol
            packet["task_call_ledger"][0]["request_params_safe"]["prior_chart_source_task_id"] = chart_source_task_id
            packet["task_call_ledger"][0]["request_params_safe"]["chart_source_task_ready"] = chart_source_task_ready
            packet["task_call_ledger"][0]["request_params_safe"]["provider_backed"] = False
            packet["task_call_ledger"][0]["request_params_safe"]["production_evidence"] = False
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
