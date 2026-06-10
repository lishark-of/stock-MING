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


def read_next_session_cache() -> dict[str, Any]:
    return packet_service.build_next_session_cache()


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
            "external": False,
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
                "external": False,
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
