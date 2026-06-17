#!/usr/bin/env python3
"""Validate the local LTG-08 Next-session ECharts map contract.

This push-gate guard does not run a browser and does not refresh market data.
It builds a local exact-cache sample and reads the current cache envelope to
keep ECharts payloads, interaction readiness, reference/zone drilldown, and
frontend read-only boundaries separate from Streamlit parity completion or
production replacement.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import command_center_next_session_projection as next_session_projection  # noqa: E402
from server.services import next_session_service, packet_service, task_service  # noqa: E402


REQUIRED_INTERACTION_KEYS = {
    "chart_payload_available",
    "drawable_series",
    "hover_evidence_contract",
    "scenario_click_drilldown",
    "reference_click_source",
    "zone_click_guardrail",
    "position_conflict_visibility",
    "deepseek_status_visibility",
    "frontend_read_only_boundary",
    "legacy_streamlit_parity",
}
REQUIRED_HOVER_FIELDS = {"price", "source", "trigger_condition", "risk_note"}
REQUIRED_NEXT_SESSION_PRODUCTION_STAGES = {
    "exact_cache_payload_contract",
    "interaction_hover_click_contract",
    "streamlit_parity_review",
    "browser_visual_qa",
    "browser_performance_trace",
    "reduced_motion_accessibility_qa",
    "durable_ci_release_evidence",
    "production_replacement_promotion",
}
REQUIRED_LEGACY_PARITY_PHASES = {
    "cache_payload_snapshot",
    "legacy_streamlit_reference_capture",
    "chart_visual_feature_matrix",
    "operation_zone_and_guardrail_parity",
    "position_conflict_and_data_trust_parity",
    "hover_click_interaction_parity",
    "browser_visual_performance_parity",
    "frontend_read_only_no_feature_loss_boundary",
    "production_replacement_promotion",
}
REQUIRED_DURABLE_EVIDENCE_KEYS = {
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
}
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


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _rows_by_key(rows: Any) -> dict[str, dict[str, Any]]:
    return {
        str(
            row.get("key")
            or row.get("criterion")
            or row.get("activation_key")
            or row.get("phase")
            or row.get("evidence_key")
            or row.get("stage_key")
            or ""
        ): row
        for row in _list(rows)
        if isinstance(row, dict)
    }


def _next_session_task(catalog: dict[str, Any]) -> dict[str, Any]:
    for task in _list(catalog.get("tasks")):
        if isinstance(task, dict) and task.get("task_type") == "build_next_session_projection":
            return task
    return {}


def _task_by_type(catalog: dict[str, Any], task_type: str) -> dict[str, Any]:
    for task in _list(catalog.get("tasks")):
        if isinstance(task, dict) and task.get("task_type") == task_type:
            return task
    return {}


def _synthetic_next_session_snapshot() -> dict[str, Any]:
    return {
        next_session_projection.PACKET_KEY: {
            "packet_key": next_session_projection.PACKET_KEY,
            "status": "ready",
            "chart_render_model": {
                "historical_series": [
                    {"x": "2026-06-08", "price": 10.0, "source": "local_contract_fixture"},
                    {"x": "2026-06-09", "close": 10.4, "source": "local_contract_fixture"},
                ],
                "scenario_series": [
                    {
                        "scenario_key": "neutral",
                        "scenario_name": "中性路径",
                        "trigger_condition": "放量但不追高",
                        "confidence_note": "中性路径只作基准",
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
                "source_packet": "position_profile",
            },
            "data_trust_summary": {
                "facts": [{"fact_key": "moneyflow", "call_status": "verified_present"}],
                "human_summary": ["真实日线：已接入", "持仓：存在冲突，需先核验"],
                "deepseek": {"label": "DeepSeek", "status": "not_called"},
            },
            "deepseek_synthesis": {"status": "not_called"},
        }
    }


def _build_exact_sample_packet() -> dict[str, Any]:
    original_snapshot = packet_service.SNAPSHOT_CACHE_PATH
    original_meta = packet_service.SQLITE_META_PATH
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        snapshot_path = temp_path / "command_center_latest.json"
        snapshot_path.write_text(json.dumps(_synthetic_next_session_snapshot(), ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = snapshot_path
        packet_service.SQLITE_META_PATH = temp_path / "meta.sqlite"
        try:
            return packet_service.build_next_session_cache()
        finally:
            packet_service.SNAPSHOT_CACHE_PATH = original_snapshot
            packet_service.SQLITE_META_PATH = original_meta


def _build_exact_service_packet() -> dict[str, Any]:
    original_snapshot = packet_service.SNAPSHOT_CACHE_PATH
    original_meta = packet_service.SQLITE_META_PATH
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        snapshot_path = temp_path / "command_center_latest.json"
        snapshot_path.write_text(json.dumps(_synthetic_next_session_snapshot(), ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = snapshot_path
        packet_service.SQLITE_META_PATH = temp_path / "meta.sqlite"
        try:
            return next_session_service.read_next_session_cache()
        finally:
            packet_service.SNAPSHOT_CACHE_PATH = original_snapshot
            packet_service.SQLITE_META_PATH = original_meta


def _next_session_production_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key in sorted(REQUIRED_NEXT_SESSION_PRODUCTION_STAGES):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": NEXT_SESSION_PRODUCTION_STAGE_LABELS[stage_key],
                "scope": "next_session_production_replacement_stage_scope_manifest",
                "current_status": "local_contract_or_runbook_only",
                "target_status": "browser_parity_or_release_evidence_required",
                "required_before_production_replacement": True,
                "exact_payload_contract_ready": stage_key in {
                    "exact_cache_payload_contract",
                    "interaction_hover_click_contract",
                },
                "interaction_contract_ready": stage_key == "interaction_hover_click_contract",
                "streamlit_parity_complete": False,
                "browser_visual_qa_done": False,
                "browser_performance_trace_done": False,
                "reduced_motion_accessibility_qa_done": False,
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
                "missing_evidence": [
                    "explicit Streamlit parity review",
                    "browser visual QA report",
                    "browser performance trace",
                    "reduced-motion/accessibility QA report",
                    "durable CI or release evidence",
                    "explicit production replacement approval",
                ],
            }
        )
    return rows


def build_contract() -> dict[str, Any]:
    exact_packet = _build_exact_sample_packet()
    exact_service_packet = _build_exact_service_packet()
    exact_chart = _dict(exact_packet.get("chart_payload"))
    chart_contract = _dict(exact_chart.get("chart_contract"))
    interaction_contract = _dict(chart_contract.get("interaction_contract"))
    series_counts = _dict(chart_contract.get("series_counts"))
    interaction_audit = _dict(exact_chart.get("interaction_readiness_audit"))
    interaction_rows = _rows_by_key(exact_chart.get("interaction_readiness_rows"))
    chart_summary = _dict(exact_packet.get("chart_summary"))
    chart_maturity = _dict(exact_chart.get("chart_maturity"))
    latest_close = _dict(exact_chart.get("latest_close_anchor"))
    scenario_anchor_rows = [row for row in _list(exact_chart.get("scenario_anchor_rows")) if isinstance(row, dict)]
    reference_line_rows = [row for row in _list(exact_chart.get("reference_line_rows")) if isinstance(row, dict)]
    zone_rows = [row for row in _list(exact_chart.get("zone_interaction_rows")) if isinstance(row, dict)]
    position_conflict = _dict(exact_chart.get("position_conflict"))
    data_trust = _dict(exact_chart.get("data_trust_summary"))
    activation_receipt = _dict(exact_service_packet.get("next_session_replacement_activation_receipt"))
    activation_rows = _rows_by_key(exact_service_packet.get("next_session_replacement_activation_rows"))
    legacy_parity_recipe = _dict(exact_service_packet.get("next_session_legacy_parity_execution_recipe"))
    legacy_parity_rows = _rows_by_key(exact_service_packet.get("next_session_legacy_parity_execution_rows"))
    browser_qa_runbook = _dict(exact_service_packet.get("next_session_browser_qa_runbook_contract"))
    browser_qa_runbook_rows = _rows_by_key(exact_service_packet.get("next_session_browser_qa_runbook_rows"))
    browser_qa_matrix_rows = [row for row in _list(exact_service_packet.get("next_session_browser_qa_matrix_rows")) if isinstance(row, dict)]
    browser_qa_evidence = _dict(exact_service_packet.get("next_session_browser_qa_evidence_summary"))
    browser_qa_evidence_rows = [row for row in _list(exact_service_packet.get("next_session_browser_qa_evidence_rows")) if isinstance(row, dict)]
    browser_qa_review = _dict(exact_service_packet.get("next_session_browser_qa_review_contract"))
    browser_qa_review_rows = _rows_by_key(exact_service_packet.get("next_session_browser_qa_review_rows"))
    durable_evidence_recipe = _dict(exact_service_packet.get("next_session_durable_evidence_recipe"))
    durable_evidence_rows = _rows_by_key(exact_service_packet.get("next_session_durable_evidence_rows"))
    production_stage_scope = _dict(exact_service_packet.get("next_session_production_stage_scope_manifest"))
    production_stage_scope_rows = _rows_by_key(exact_service_packet.get("next_session_production_stage_scope_rows"))

    current_cache = next_session_service.read_next_session_cache()
    current_ledger = [row for row in _list(current_cache.get("call_ledger")) if isinstance(row, dict)]
    task_catalog = task_service.build_task_catalog()
    task = _next_session_task(task_catalog)
    browser_qa_task = _task_by_type(task_catalog, "run_next_session_browser_qa_review")
    browser_qa_review_status = browser_qa_review.get("status")
    browser_qa_review_pending = (
        browser_qa_review_status == "next_session_browser_qa_review_pending"
        and browser_qa_review.get("explicit_review_task_done") is False
        and browser_qa_review.get("local_browser_qa_review_ready") is False
        and _dict(browser_qa_review_rows.get("explicit_post_review_task")).get("status") == "pending_explicit_post"
    )
    browser_qa_review_ready = (
        browser_qa_review_status == "next_session_browser_qa_review_ready_local_artifact"
        and browser_qa_review.get("explicit_review_task_done") is True
        and browser_qa_review.get("local_browser_qa_review_ready") is True
        and _dict(browser_qa_review_rows.get("explicit_post_review_task")).get("status") == "passed"
        and _dict(browser_qa_review_rows.get("next_route_evidence_available")).get("status") == "passed"
        and _dict(browser_qa_review_rows.get("visual_evidence_passed")).get("status") == "passed"
        and _dict(browser_qa_review_rows.get("performance_evidence_passed")).get("status") == "passed"
        and _dict(browser_qa_review_rows.get("default_and_reduced_motion_coverage")).get("status") == "passed"
    )
    next_page = _read_script("desktop/src/routes/NextSessionMap.tsx")
    chart_component = _read_script("desktop/src/components/NextSessionChart.tsx")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/next_session_map_contract.py")
    static_production_stage_scope_rows = _next_session_production_stage_scope_rows()

    rows = [
        _row(
            "exact_echarts_payload_has_complete_chart_contract",
            exact_packet.get("packet_key") == next_session_projection.PACKET_KEY
            and exact_packet.get("status") == "ready"
            and exact_chart.get("status") == "ready"
            and exact_chart.get("is_exact_next_session_packet") is True
            and exact_chart.get("uses_real_daily_close") is True
            and chart_contract.get("schema_version") == "next_session_echarts_payload.v1"
            and chart_contract.get("renderer") == "ECharts"
            and chart_contract.get("source_packet") == next_session_projection.PACKET_KEY
            and int(series_counts.get("historical_points") or 0) >= 2
            and int(series_counts.get("scenario_series") or 0) >= 1
            and int(series_counts.get("reference_lines") or 0) >= 4
            and int(series_counts.get("operation_zones") or 0) >= 1
            and latest_close.get("price") == 10.4
            and chart_maturity.get("status") == "ready"
            and chart_summary.get("maturity_status") == "ready"
            and chart_summary.get("has_drawable_data") is True,
            "Synthetic exact next-session packet must normalize into a complete ECharts payload with real-close anchor, references, zones, and drawable series.",
        ),
        _row(
            "interaction_readiness_is_ready_but_parity_pending",
            interaction_audit.get("schema_version") == "next_session_interaction_readiness.v1"
            and interaction_audit.get("status") == "interaction_contract_ready_parity_pending"
            and interaction_audit.get("blocking_count") == 0
            and interaction_audit.get("ready_count", 0) >= 8
            and interaction_audit.get("pending_count", 0) >= 1
            and interaction_audit.get("streamlit_parity_complete") is False
            and interaction_audit.get("production_replacement_complete") is False
            and REQUIRED_INTERACTION_KEYS.issubset(set(interaction_rows))
            and _dict(interaction_rows.get("hover_evidence_contract")).get("status") == "ready"
            and _dict(interaction_rows.get("zone_click_guardrail")).get("status") == "ready"
            and _dict(interaction_rows.get("frontend_read_only_boundary")).get("status") == "ready"
            and _dict(interaction_rows.get("legacy_streamlit_parity")).get("status") == "pending"
            and _flag_false(interaction_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and interaction_audit.get("does_not_execute_trades") is True
            and interaction_audit.get("does_not_modify_action") is True
            and interaction_audit.get("does_not_modify_operation_zones") is True,
            "Interaction readiness must expose hover/click/source/guardrail readiness while keeping Streamlit parity and production replacement pending.",
        ),
        _row(
            "chart_contract_is_read_only_no_external_no_action",
            chart_contract.get("cache_only") is True
            and _flag_false(chart_contract, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called", "frontend_computes_trade_action")
            and chart_contract.get("does_not_execute_trades") is True
            and chart_contract.get("does_not_modify_action") is True
            and chart_contract.get("does_not_modify_operation_zones") is True
            and chart_contract.get("requires_button_task_for_refresh") is True
            and set(_list(interaction_contract.get("hover_displays"))) == REQUIRED_HOVER_FIELDS
            and interaction_contract.get("source_endpoint") == "GET /api/next-session/cache"
            and interaction_contract.get("frontend_render_only") is True
            and interaction_contract.get("frontend_must_not_calculate_action") is True,
            "Chart contract must remain cache-only and frontend-render-only with no provider/model calls, trades, action computation, or operation-zone mutation.",
        ),
        _row(
            "reference_zone_position_deepseek_status_are_visible",
            bool(reference_line_rows)
            and all(row.get("frontend_mutable") is False for row in reference_line_rows)
            and bool(zone_rows)
            and all(row.get("click_displays") == "guardrail" and row.get("frontend_mutable") is False for row in zone_rows)
            and scenario_anchor_rows
            and all(row.get("anchored_to_latest_close") is True for row in scenario_anchor_rows)
            and position_conflict.get("has_conflict") is True
            and "cost_price_conflict" in _list(position_conflict.get("conflict_flags"))
            and bool(_list(data_trust.get("facts")))
            and exact_chart.get("deepseek_status") == "not_called",
            "Reference-line sources, operation-zone guardrails, latest-close anchoring, position conflicts, data trust, and DeepSeek status must be visible in the cache payload.",
        ),
        _row(
            "current_get_cache_envelope_is_read_only",
            current_cache.get("packet_key") == next_session_projection.PACKET_KEY
            and current_cache.get("does_not_modify_action") is not False
            and current_cache.get("does_not_modify_operation_zones") is not False
            and _flag_false(current_cache, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and len(current_ledger) >= 1
            and all(
                row.get("api")
                in {
                    "local_next_session_cache",
                    "local_next_session_browser_qa_review",
                    "local_next_session_durable_evidence_recipe",
                    "local_next_session_production_stage_scope_manifest",
                }
                for row in current_ledger
            )
            and all(row.get("external") is False for row in current_ledger)
            and all(_flag_false(row, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called") for row in current_ledger)
            and all(row.get("does_not_execute_trades") is True for row in current_ledger)
            and all(row.get("does_not_modify_strategy_action") is True for row in current_ledger)
            and all(row.get("does_not_modify_operation_zones") is True for row in current_ledger),
            "Current GET next-session cache envelope must stay local/read-only even when the exact packet is missing.",
        ),
        _row(
            "replacement_activation_receipt_guides_next_safe_step",
            activation_receipt.get("schema_version") == "next_session_replacement_activation_receipt.v1"
            and activation_receipt.get("status") == "next_session_activation_receipt_ready_replacement_blocked"
            and activation_receipt.get("scope") == "local_next_session_replacement_activation_receipt_no_browser_no_provider"
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("production_replacement_complete") is False
            and activation_receipt.get("streamlit_parity_complete") is False
            and activation_receipt.get("browser_visual_qa_done") is False
            and activation_receipt.get("browser_performance_trace_done") is False
            and activation_receipt.get("durable_ci_evidence_complete") is False
            and activation_receipt.get("allowed_next_step")
            == "explicit_streamlit_parity_browser_visual_performance_review_then_replacement_promotion"
            and set(activation_receipt.get("missing_evidence_items") or []).issuperset(
                {"streamlit_parity_review", "browser_visual_qa", "browser_performance_trace", "durable_ci_or_release_evidence"}
            )
            and _dict(activation_rows.get("exact_echarts_payload_ready")).get("status") == "passed"
            and _dict(activation_rows.get("interaction_readiness_ready")).get("status") == "passed"
            and _dict(activation_rows.get("reference_zone_context_visible")).get("status") == "passed"
            and _dict(activation_rows.get("frontend_read_only_boundary")).get("status") == "passed"
            and _dict(activation_rows.get("streamlit_parity_review_required")).get("status") == "pending_streamlit_parity_review"
            and _dict(activation_rows.get("browser_visual_qa_required")).get("status") == "pending_browser_visual_qa"
            and _dict(activation_rows.get("browser_performance_trace_required")).get("status")
            == "pending_browser_performance_trace"
            and _dict(activation_rows.get("durable_ci_or_release_evidence_required")).get("status")
            == "pending_durable_evidence"
            and _flag_false(activation_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and activation_receipt.get("does_not_modify_operation_zones") is True,
            "Replacement activation receipt must guide Streamlit parity, browser QA, performance trace, and durable evidence without claiming production replacement.",
        ),
        _row(
            "legacy_parity_execution_recipe_is_no_feature_loss_pending",
            legacy_parity_recipe.get("schema_version") == "next_session_legacy_parity_execution_recipe.v1"
            and legacy_parity_recipe.get("status") == "next_session_legacy_parity_recipe_ready_execution_pending"
            and legacy_parity_recipe.get("scope") == "local_next_session_legacy_parity_recipe_no_browser_no_provider"
            and legacy_parity_recipe.get("local_recipe_ready") is True
            and legacy_parity_recipe.get("execution_done") is False
            and legacy_parity_recipe.get("streamlit_parity_complete") is False
            and legacy_parity_recipe.get("production_replacement_complete") is False
            and legacy_parity_recipe.get("no_feature_loss_required") is True
            and set(legacy_parity_recipe.get("pending_phases") or []) == REQUIRED_LEGACY_PARITY_PHASES
            and int(legacy_parity_recipe.get("pending_phase_count") or 0) == len(REQUIRED_LEGACY_PARITY_PHASES)
            and int(legacy_parity_recipe.get("row_count") or 0) == len(REQUIRED_LEGACY_PARITY_PHASES)
            and {
                "latest close anchor",
                "scenario paths",
                "reference and limit lines",
                "operation zones and guardrails",
                "position conflict warnings",
                "freshness and data trust",
                "DeepSeek status display",
                "hover and click drilldown",
                "read-only action boundary",
            }.issubset(set(legacy_parity_recipe.get("preserved_feature_groups") or []))
            and {
                "legacy Streamlit reference capture",
                "feature-by-feature parity matrix",
                "browser visual QA across default and reduced motion",
                "browser performance trace",
                "durable CI or release evidence",
            }.issubset(set(legacy_parity_recipe.get("required_evidence") or []))
            and "drop_legacy_signal_groups_to_reduce_scope" in set(legacy_parity_recipe.get("not_allowed_next_steps") or [])
            and "compute_strategy_action_in_frontend" in set(legacy_parity_recipe.get("not_allowed_next_steps") or [])
            and set(legacy_parity_rows) == REQUIRED_LEGACY_PARITY_PHASES
            and _dict(legacy_parity_rows.get("cache_payload_snapshot")).get("status") == "ready_local_contract"
            and _dict(legacy_parity_rows.get("legacy_streamlit_reference_capture")).get("status")
            == "pending_legacy_reference"
            and _dict(legacy_parity_rows.get("frontend_read_only_no_feature_loss_boundary")).get("status")
            == "ready_local_contract"
            and all(row.get("parity_complete") is False for row in legacy_parity_rows.values())
            and all(row.get("required_before_production_replacement") is True for row in legacy_parity_rows.values())
            and all(row.get("opens_no_browser") is True for row in legacy_parity_rows.values())
            and all(row.get("writes_no_artifacts") is True for row in legacy_parity_rows.values())
            and all(row.get("external_calls_triggered") is False for row in legacy_parity_rows.values())
            and all(row.get("tushare_called") is False for row in legacy_parity_rows.values())
            and all(row.get("deepseek_called") is False for row in legacy_parity_rows.values())
            and all(row.get("github_called") is False for row in legacy_parity_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in legacy_parity_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in legacy_parity_rows.values())
            and all(row.get("does_not_modify_operation_zones") is True for row in legacy_parity_rows.values())
            and all(row.get("frontend_computes_trade_action") is False for row in legacy_parity_rows.values())
            and all(row.get("contains_secret") is False for row in legacy_parity_rows.values())
            and _flag_false(legacy_parity_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and legacy_parity_recipe.get("does_not_execute_trades") is True
            and legacy_parity_recipe.get("does_not_modify_strategy_action") is True
            and legacy_parity_recipe.get("does_not_modify_operation_zones") is True
            and legacy_parity_recipe.get("frontend_computes_trade_action") is False,
            "Legacy parity recipe must require no-feature-loss Streamlit comparison while staying local-only and pending.",
        ),
        _row(
            "next_session_task_is_button_gated_local_cache_pipeline",
            task.get("route") == "POST /api/next-session/generate"
            and task.get("button_gated") is True
            and task.get("current_backend") == "local_cache_pipeline"
            and task.get("external_call_policy") == "local_cache_only_current_mvp"
            and task.get("possible_external_sources") == []
            and task.get("call_ledger_required") is True
            and task.get("does_not_execute_trades") is True
            and task.get("does_not_modify_strategy_action") is True
            and _dict(task.get("retry_policy")).get("auto_retry_on_get") is False
            and _dict(task.get("lock_policy")).get("cache_api_can_acquire_lock") is False
            and _dict(task.get("dedupe_policy")).get("cache_api_can_dedupe") is False,
            "Next-session generation remains a button-gated local cache pipeline; GET cache cannot retry, lock, dedupe, refresh providers, or execute trades.",
        ),
        _row(
            "next_session_browser_qa_runbook_and_evidence_are_local_only",
            browser_qa_runbook.get("schema_version") == "next_session_browser_qa_runbook.v1"
            and browser_qa_runbook.get("scope") == "local_next_session_browser_qa_runbook_not_browser_execution"
            and browser_qa_runbook.get("status") == "next_session_browser_qa_runbook_ready_execution_pending"
            and browser_qa_runbook.get("local_runbook_ready") is True
            and browser_qa_runbook.get("next_route") == "#next"
            and browser_qa_runbook.get("artifact_root") == ".stock_ming_3/motion_qa"
            and browser_qa_runbook.get("opens_no_browser") is True
            and browser_qa_runbook.get("writes_no_artifacts") is True
            and browser_qa_runbook.get("production_replacement_complete") is False
            and browser_qa_runbook.get("streamlit_parity_complete") is False
            and len(browser_qa_matrix_rows) == 4
            and {row.get("viewport") for row in browser_qa_matrix_rows} == {"desktop", "laptop", "tablet", "mobile"}
            and _dict(browser_qa_runbook_rows.get("next_session_browser_qa_runbook_ready")).get("status") == "passed_static_policy"
            and browser_qa_evidence.get("schema_version") == "next_session_browser_qa_evidence.v1"
            and browser_qa_evidence.get("scope") == "local_next_session_browser_qa_evidence_reader_no_browser_execution"
            and browser_qa_evidence.get("next_route") == "#next"
            and browser_qa_evidence.get("reads_ignored_local_reports_only") is True
            and browser_qa_evidence.get("screenshots_are_not_tracked") is True
            and browser_qa_evidence.get("report_artifacts_are_not_tracked") is True
            and browser_qa_evidence.get("production_replacement_complete") is False
            and browser_qa_evidence.get("streamlit_parity_complete") is False
            and len(browser_qa_evidence_rows) == int(browser_qa_evidence.get("row_count") or 0)
            and _flag_false(browser_qa_runbook, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and _flag_false(browser_qa_evidence, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Next-session browser QA runbook/evidence must stay local-only and separate local artifact summaries from Streamlit parity or production replacement.",
        ),
        _row(
            "next_session_browser_qa_review_is_button_gated_local_only",
            browser_qa_task.get("route") == "POST /api/next-session/browser-qa-review"
            and browser_qa_task.get("button_gated") is True
            and browser_qa_task.get("browser_qa_review_only") is True
            and browser_qa_task.get("opens_browser") is False
            and browser_qa_task.get("starts_servers") is False
            and browser_qa_task.get("writes_artifacts") is False
            and browser_qa_task.get("reads_ignored_local_reports_only") is True
            and browser_qa_task.get("production_replacement_complete") is False
            and browser_qa_task.get("does_not_execute_trades") is True
            and browser_qa_review.get("schema_version") == "next_session_browser_qa_review.v1"
            and browser_qa_review.get("scope") == "button_gated_local_next_session_browser_qa_review_no_browser_execution"
            and (browser_qa_review_pending or browser_qa_review_ready)
            and browser_qa_review.get("production_replacement_complete") is False
            and browser_qa_review.get("streamlit_parity_complete") is False
            and browser_qa_review.get("opens_no_browser") is True
            and browser_qa_review.get("writes_no_artifacts") is True
            and _dict(browser_qa_review_rows.get("streamlit_parity_stays_pending")).get("status") == "passed"
            and _dict(browser_qa_review_rows.get("production_replacement_stays_blocked")).get("status") == "passed"
            and _flag_false(browser_qa_review, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Next-session browser QA review must be explicit POST/local artifact only when ready, or remain pending before POST; neither state may execute a browser or promote production replacement.",
        ),
        _row(
            "next_session_durable_evidence_recipe_is_local_production_pending",
            durable_evidence_recipe.get("schema_version")
            == next_session_service.NEXT_SESSION_DURABLE_EVIDENCE_SCHEMA_VERSION
            and durable_evidence_recipe.get("status")
            == "next_session_durable_evidence_recipe_ready_production_pending"
            and durable_evidence_recipe.get("scope")
            == "local_next_session_durable_evidence_recipe_no_browser_no_provider"
            and durable_evidence_recipe.get("local_recipe_ready") is True
            and durable_evidence_recipe.get("durable_evidence_complete") is False
            and durable_evidence_recipe.get("durable_promotion_ready") is False
            and durable_evidence_recipe.get("production_replacement_complete") is False
            and durable_evidence_recipe.get("streamlit_parity_complete") is False
            and durable_evidence_recipe.get("streamlit_reference_captured") is False
            and durable_evidence_recipe.get("feature_by_feature_parity_complete") is False
            and durable_evidence_recipe.get("hover_click_parity_complete") is False
            and durable_evidence_recipe.get("browser_visual_performance_reviewed") is False
            and durable_evidence_recipe.get("durable_ci_evidence_complete") is False
            and durable_evidence_recipe.get("provider_execution_implemented") is False
            and durable_evidence_recipe.get("model_execution_implemented") is False
            and durable_evidence_recipe.get("worker_execution_implemented") is False
            and durable_evidence_recipe.get("cache_get_external_calls") is False
            and durable_evidence_recipe.get("react_render_external_calls") is False
            and durable_evidence_recipe.get("page_render_starts_browser") is False
            and durable_evidence_recipe.get("page_render_starts_provider") is False
            and durable_evidence_recipe.get("page_render_starts_model") is False
            and durable_evidence_recipe.get("evidence_keys")
            == list(next_session_service.NEXT_SESSION_DURABLE_EVIDENCE_KEYS)
            and set(durable_evidence_rows) == REQUIRED_DURABLE_EVIDENCE_KEYS
            and int(durable_evidence_recipe.get("row_count") or 0) == len(durable_evidence_rows)
            and int(durable_evidence_recipe.get("evidence_key_count") or 0)
            == len(next_session_service.NEXT_SESSION_DURABLE_EVIDENCE_KEYS)
            and int(durable_evidence_recipe.get("durable_evidence_blocker_count") or 0) >= 5
            and "same-packet Streamlit reference capture" in _list(durable_evidence_recipe.get("required_evidence"))
            and "durable browser visual/performance evidence for #next"
            in _list(durable_evidence_recipe.get("required_evidence"))
            and "durable CI or release evidence" in _list(durable_evidence_recipe.get("required_evidence"))
            and "treat durable recipe as ECharts production replacement"
            in _list(durable_evidence_recipe.get("not_allowed_next_steps"))
            and "treat local browser artifact review as durable evidence"
            in _list(durable_evidence_recipe.get("not_allowed_next_steps"))
            and "call Tushare or DeepSeek from GET cache or React render"
            in _list(durable_evidence_recipe.get("not_allowed_next_steps"))
            and _dict(durable_evidence_rows.get("cache_render_boundary_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("exact_echarts_payload_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("interaction_contract_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("legacy_parity_recipe_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("browser_qa_runbook_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("local_browser_qa_review_visible")).get("passed") is True
            and _dict(durable_evidence_rows.get("streamlit_reference_capture_required")).get("production_blocker")
            is True
            and _dict(durable_evidence_rows.get("durable_browser_visual_performance_evidence_required")).get(
                "production_blocker"
            )
            is True
            and _dict(durable_evidence_rows.get("no_provider_trade_action_secret_boundary")).get("passed") is True
            and _flag_false(
                durable_evidence_recipe,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
                "frontend_computes_trade_action",
            )
            and durable_evidence_recipe.get("does_not_execute_trades") is True
            and durable_evidence_recipe.get("does_not_modify_strategy_action") is True
            and durable_evidence_recipe.get("does_not_modify_operation_zones") is True
            and any(
                _dict(row).get("api") == "local_next_session_durable_evidence_recipe"
                for row in _list(durable_evidence_recipe.get("call_ledger"))
            )
            and "next_session_durable_evidence_recipe" in next_page,
            "Next-session durable evidence recipe must pin remaining Streamlit parity, browser visual/performance, CI/release, and promotion evidence without opening a browser, calling providers/models, executing trades, or claiming ECharts production replacement.",
        ),
        _row(
            "production_replacement_stage_scope_manifest_is_cache_visible_and_pending",
            production_stage_scope.get("schema_version")
            == next_session_service.NEXT_SESSION_PRODUCTION_STAGE_SCOPE_SCHEMA_VERSION
            and production_stage_scope.get("status")
            == "next_session_production_stage_scope_manifest_ready_production_pending"
            and production_stage_scope.get("scope") == "next_session_production_replacement_stage_scope_manifest"
            and production_stage_scope.get("local_manifest_ready") is True
            and set(production_stage_scope_rows)
            == REQUIRED_NEXT_SESSION_PRODUCTION_STAGES
            and len(production_stage_scope_rows) == len(REQUIRED_NEXT_SESSION_PRODUCTION_STAGES)
            and production_stage_scope.get("stage_keys")
            == list(next_session_service.NEXT_SESSION_PRODUCTION_STAGE_KEYS)
            and int(production_stage_scope.get("stage_count") or 0) == len(REQUIRED_NEXT_SESSION_PRODUCTION_STAGES)
            and int(production_stage_scope.get("direct_evidence_stage_count") or 0)
            == len(_list(production_stage_scope.get("direct_evidence_stage_keys")))
            and set(_list(production_stage_scope.get("direct_evidence_stage_keys"))).issubset(
                {"browser_visual_qa", "browser_performance_trace", "reduced_motion_accessibility_qa"}
            )
            and int(production_stage_scope.get("pending_stage_count") or 0)
            + int(production_stage_scope.get("direct_evidence_stage_count") or 0)
            == len(REQUIRED_NEXT_SESSION_PRODUCTION_STAGES)
            and all(
                row.get("scope") == "next_session_production_replacement_stage_scope_manifest"
                for row in production_stage_scope_rows.values()
            )
            and all(
                row.get("required_before_production_replacement") is True
                for row in production_stage_scope_rows.values()
            )
            and all(
                row.get("current_status")
                in {
                    "local_contract_ready",
                    "pending_exact_cache_payload",
                    "pending_interaction_contract",
                    "pending_same_packet_streamlit_parity",
                    "direct_evidence_ready_local_artifact",
                    "pending_browser_visual_qa_review",
                    "pending_browser_performance_trace_review",
                    "pending_reduced_motion_accessibility_review",
                    "pending_durable_ci_release_evidence",
                    "pending_production_replacement_promotion",
                }
                for row in production_stage_scope_rows.values()
            )
            and all(
                row.get("target_status") == "browser_parity_or_release_evidence_required"
                for row in production_stage_scope_rows.values()
            )
            and _dict(production_stage_scope_rows.get("exact_cache_payload_contract")).get("local_contract_ready")
            is True
            and _dict(production_stage_scope_rows.get("interaction_hover_click_contract")).get(
                "local_contract_ready"
            )
            is True
            and all(row.get("streamlit_parity_complete") is False for row in production_stage_scope_rows.values())
            and all(row.get("durable_ci_evidence_complete") is False for row in production_stage_scope_rows.values())
            and all(row.get("production_replacement_complete") is False for row in production_stage_scope_rows.values())
            and all(row.get("browser_opened_by_contract") is False for row in production_stage_scope_rows.values())
            and all(row.get("artifacts_written_by_contract") is False for row in production_stage_scope_rows.values())
            and all(row.get("external_calls_triggered") is False for row in production_stage_scope_rows.values())
            and all(row.get("tushare_called") is False for row in production_stage_scope_rows.values())
            and all(row.get("deepseek_called") is False for row in production_stage_scope_rows.values())
            and all(row.get("github_called") is False for row in production_stage_scope_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in production_stage_scope_rows.values())
            and all(
                row.get("does_not_modify_strategy_action") is True for row in production_stage_scope_rows.values()
            )
            and all(
                row.get("does_not_modify_operation_zones") is True for row in production_stage_scope_rows.values()
            )
            and all(row.get("frontend_computes_trade_action") is False for row in production_stage_scope_rows.values())
            and all(row.get("contains_secret") is False for row in production_stage_scope_rows.values())
            and _flag_false(
                production_stage_scope,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
                "frontend_computes_trade_action",
            )
            and production_stage_scope.get("does_not_execute_trades") is True
            and production_stage_scope.get("does_not_modify_strategy_action") is True
            and production_stage_scope.get("does_not_modify_operation_zones") is True
            and any(
                _dict(row).get("api") == "local_next_session_production_stage_scope_manifest"
                for row in _list(production_stage_scope.get("call_ledger"))
            )
            and "next_session_production_stage_scope_manifest" in next_page
            and "productionStageScope" in next_page,
            "Next-session production stage scope must be visible from cache/UI and reduce only local direct-evidence blockers while keeping Streamlit parity, durable CI/release evidence, and production replacement pending.",
        ),
        _row(
            "react_echarts_frontend_uses_api_client_and_read_only_display",
            "getNextSessionCache" in next_page
            and 'postTask("/api/next-session/generate")' in next_page
            and 'postTask("/api/next-session/browser-qa-review"' in next_page
            and "next_session_browser_qa_evidence_summary" in next_page
            and "next_session_browser_qa_review_contract" in next_page
            and "next_session_durable_evidence_recipe" in next_page
            and "durableEvidenceRecipe" in next_page
            and "NextSessionChart" in next_page
            and "frontend_computes_trade_action" in next_page
            and "does_not_modify_operation_zones" in next_page
            and "useReducedMotionPreference" in chart_component
            and "tooltipFormatter" in chart_component
            and "handleChartClick" in chart_component
            and "setSelectedInsight" in chart_component
            and "不会计算 action" in chart_component
            and "前端不修改价格、持仓、operation_zones 或 strategy action" in chart_component
            and "fetch(" not in next_page
            and "axios" not in next_page
            and ("tushare" + "_adapter") not in next_page
            and "pro_api" not in next_page
            and "process.env" not in next_page,
            "React route must use the FastAPI client and ECharts must only display tooltips/click insight without computing action or mutating packet values.",
        ),
        _row(
            "push_gate_runs_next_session_contract_after_deepseek",
            "scripts/next_session_map_contract.py" in push_gate_script
            and "Next-session map contract" in push_gate_script
            and "next_session_map_contract: passed_local_contract_streamlit_parity_pending" in push_gate_script
            and push_gate_script.find('run_step "DeepSeek governance contract"') < push_gate_script.find('run_step "Next-session map contract"')
            and push_gate_script.find('run_step "Next-session map contract"') < push_gate_script.find('run_step "Candidate Radar contract"'),
            "Push gate must run LTG-08 Next-session map after DeepSeek governance and before Candidate Radar.",
        ),
        _row(
            "script_is_local_no_browser_or_provider_execution",
            "command_center_3_next_session_map_contract.v1" in this_script
            and "local_next_session_map_contract_no_browser_no_provider" in this_script
            and "next_session_replacement_activation_receipt.v1" in this_script
            and "next_session_durable_evidence_recipe.v1" in this_script
            and "next_session_production_replacement_stage_scope_manifest" in this_script
            and "production_replacement_complete" in this_script
            and "streamlit_parity_complete" in this_script
            and "browser_visual_qa_done" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script
            and ("deepseek" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients, browser automation, or network libraries.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_next_session_map_contract.v1",
        "status": "next_session_map_contract_passed" if not blockers else "next_session_map_contract_blocked",
        "scope": "local_next_session_map_contract_no_browser_no_provider",
        "ltg": "LTG-08/LTG-11",
        "contract_ready": not blockers,
        "exact_echarts_payload_ready": True,
        "interaction_contract_ready": True,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "replacement_activation_receipt_ready": activation_receipt.get("local_activation_receipt_ready") is True,
        "legacy_parity_recipe_ready": legacy_parity_recipe.get("local_recipe_ready") is True,
        "durable_evidence_recipe_ready": durable_evidence_recipe.get("local_recipe_ready") is True,
        "durable_evidence_complete": False,
        "durable_evidence_blocker_count": durable_evidence_recipe.get("durable_evidence_blocker_count", 0),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "frontend_computes_trade_action": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "exact_chart_status": exact_chart.get("status"),
            "chart_maturity_status": chart_maturity.get("status"),
            "interaction_status": interaction_audit.get("status"),
            "interaction_blocking_count": interaction_audit.get("blocking_count"),
            "streamlit_parity_complete": interaction_audit.get("streamlit_parity_complete"),
            "production_replacement_complete": interaction_audit.get("production_replacement_complete"),
            "replacement_activation_receipt_status": activation_receipt.get("status"),
            "replacement_activation_production_blocker_count": activation_receipt.get("production_blocker_count"),
            "legacy_parity_recipe_status": legacy_parity_recipe.get("status"),
            "legacy_parity_pending_phase_count": legacy_parity_recipe.get("pending_phase_count"),
            "legacy_parity_phase_keys": sorted(row.get("phase") for row in legacy_parity_rows.values()),
            "durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
            "durable_evidence_ready": durable_evidence_recipe.get("local_recipe_ready"),
            "durable_evidence_blocker_count": durable_evidence_recipe.get("durable_evidence_blocker_count"),
            "durable_evidence_missing": durable_evidence_recipe.get("missing_durable_evidence"),
            "historical_point_count": series_counts.get("historical_points"),
            "scenario_series_count": series_counts.get("scenario_series"),
            "reference_line_count": series_counts.get("reference_lines"),
            "operation_zone_count": series_counts.get("operation_zones"),
            "current_cache_status": current_cache.get("status"),
            "current_cache_call_status": current_ledger[0].get("call_status") if current_ledger else None,
            "task_backend": task.get("current_backend"),
            "production_stage_scope_status": production_stage_scope.get("status"),
            "production_stage_scope_count": len(production_stage_scope_rows),
            "production_stage_scope_keys": sorted(production_stage_scope_rows),
            "production_stage_scope_direct_evidence_count": production_stage_scope.get("direct_evidence_stage_count"),
            "production_stage_scope_pending_count": production_stage_scope.get("pending_stage_count"),
            "static_production_stage_scope_count": len(static_production_stage_scope_rows),
        },
        "legacy_parity_execution_rows": list(legacy_parity_rows.values()),
        "durable_evidence_rows": list(durable_evidence_rows.values()),
        "production_replacement_stage_scope_rows": list(production_stage_scope_rows.values()),
        "static_production_replacement_stage_scope_rows": static_production_stage_scope_rows,
        "rows": rows,
        "note": "This is a local push-gate contract. Browser visual QA, performance trace, legacy Streamlit parity, and production ECharts replacement remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-08 Next-session ECharts map contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"next_session_map_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "streamlit_parity_complete: false; production_replacement_complete: false; "
            "browser_visual_qa_done: false".format(**contract)
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
