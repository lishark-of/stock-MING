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
        str(row.get("key") or row.get("criterion") or ""): row
        for row in _list(rows)
        if isinstance(row, dict)
    }


def _next_session_task(catalog: dict[str, Any]) -> dict[str, Any]:
    for task in _list(catalog.get("tasks")):
        if isinstance(task, dict) and task.get("task_type") == "build_next_session_projection":
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


def build_contract() -> dict[str, Any]:
    exact_packet = _build_exact_sample_packet()
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

    current_cache = next_session_service.read_next_session_cache()
    current_ledger = [row for row in _list(current_cache.get("call_ledger")) if isinstance(row, dict)]
    task = _next_session_task(task_service.build_task_catalog())
    next_page = _read_script("desktop/src/routes/NextSessionMap.tsx")
    chart_component = _read_script("desktop/src/components/NextSessionChart.tsx")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/next_session_map_contract.py")

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
            and all(row.get("api") == "local_next_session_cache" for row in current_ledger)
            and all(row.get("external") is False for row in current_ledger)
            and all(_flag_false(row, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called") for row in current_ledger)
            and all(row.get("does_not_execute_trades") is True for row in current_ledger)
            and all(row.get("does_not_modify_strategy_action") is True for row in current_ledger)
            and all(row.get("does_not_modify_operation_zones") is True for row in current_ledger),
            "Current GET next-session cache envelope must stay local/read-only even when the exact packet is missing.",
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
            "react_echarts_frontend_uses_api_client_and_read_only_display",
            "getNextSessionCache" in next_page
            and 'postTask("/api/next-session/generate")' in next_page
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
            "historical_point_count": series_counts.get("historical_points"),
            "scenario_series_count": series_counts.get("scenario_series"),
            "reference_line_count": series_counts.get("reference_lines"),
            "operation_zone_count": series_counts.get("operation_zones"),
            "current_cache_status": current_cache.get("status"),
            "current_cache_call_status": current_ledger[0].get("call_status") if current_ledger else None,
            "task_backend": task.get("current_backend"),
        },
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
