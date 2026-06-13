from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import packet_service
from .task_service import create_task_record, update_task_status

SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"


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
    packet["next_session_replacement_activation_receipt"] = activation_receipt
    packet["next_session_replacement_activation_rows"] = activation_rows
    packet["next_session_activation_receipt_ready"] = activation_receipt["local_activation_receipt_ready"]
    packet["next_session_activation_production_blocker_count"] = activation_receipt["production_blocker_count"]
    packet["next_session_activation_missing_evidence_count"] = activation_receipt["missing_evidence_count"]
    packet.setdefault("call_ledger", _next_session_cache_call_ledger(packet, _now_iso()))
    packet.setdefault(
        "warnings",
        [
            "GET /api/next-session/cache 只读取本地次日图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
            " next_session_replacement_activation_receipt 只是替代验收路径，不运行浏览器、不证明生产替代完成。"
        ],
    )
    return packet


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
