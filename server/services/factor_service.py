from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_serenity_method_radar as serenity_radar
from storage.sqlite_meta import SQLiteMetaStore

from . import packet_service, storage_service
from .task_service import create_task_record, create_task_stub, update_task_status

SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def read_factor_quant_cache() -> dict[str, Any]:
    packet = dict(packet_service.build_factor_quant_cache())
    cache_ledger = _factor_quant_cache_call_ledger(packet, _now_iso())
    existing_ledger = packet.get("call_ledger") if isinstance(packet.get("call_ledger"), list) else []
    packet["cache_call_ledger"] = cache_ledger
    packet["call_ledger"] = cache_ledger + list(existing_ledger)
    cache_warning = "GET /api/factor-quant/cache 只读取本地多因子图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
    existing_warnings = packet.get("warnings") if isinstance(packet.get("warnings"), list) else []
    packet["warnings"] = [cache_warning] + [item for item in existing_warnings if item != cache_warning]
    return packet


def _factor_quant_cache_call_ledger(packet: dict[str, Any], now: str) -> list[dict[str, Any]]:
    runtime = packet.get("runtime") if isinstance(packet.get("runtime"), dict) else {}
    values = runtime.get("factor_values") if isinstance(runtime.get("factor_values"), list) else []
    return [
        {
            "api": "local_factor_quant_cache",
            "request_params_safe": {
                "packet_key": packet.get("packet_key"),
                "mode": packet.get("mode"),
                "status": packet.get("status"),
                "cache_source": packet.get("cache_source"),
                "runtime_status": runtime.get("status"),
            },
            "row_count": len(values),
            "data_date": packet.get("trade_date") or packet.get("data_date"),
            "local_fetched_at": now,
            "call_status": "cache_missing" if packet.get("status") == "cache_missing" else "cache_read",
            "error_message_safe": "",
            "external": False,
        }
    ]


def _snapshot_value(snapshot: dict[str, Any], key: str) -> Any:
    return snapshot.get(key)


def _target_from_payload_or_snapshot(payload: Any, snapshot: dict[str, Any]) -> str:
    if isinstance(payload, dict):
        for key in ("ts_code", "ticker", "symbol"):
            if payload.get(key):
                return str(payload[key])
    for packet_key in ("moneyflow_packet", "strategy_packet", "decision_packet", "projection_packet"):
        packet = snapshot.get(packet_key)
        if isinstance(packet, dict):
            for key in ("ticker", "target", "ts_code"):
                if packet.get(key):
                    return str(packet[key])
    return "current_target"


def _local_snapshot_call_ledger(snapshot: dict[str, Any], now: str) -> list[dict[str, Any]]:
    loaded_keys = [
        key
        for key in (
            "moneyflow_packet",
            "hard_risk_packet",
            "limit_emotion_packet",
            "chip_packet",
            "strategy_packet",
            "decision_packet",
            "quant_packet",
            "a_share_fact_lineage_summary",
        )
        if key in snapshot
    ]
    return [
        {
            "api": "local_snapshot_cache",
            "request_params_safe": {"packet_keys": loaded_keys},
            "row_count": len(loaded_keys),
            "data_date": snapshot.get("timestamp"),
            "local_fetched_at": now,
            "call_status": "cache_read" if loaded_keys else "cache_missing",
            "error_message_safe": "",
        }
    ]


def _factor_values_storage_call_ledger(result: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        "api": "local_parquet_factor_values",
        "request_params_safe": {
            "dataset": "factor_values",
            "path": result.get("path"),
        },
        "row_count": int(result.get("row_count") or 0),
        "data_date": None,
        "local_fetched_at": now,
        "call_status": result.get("status") or "unknown",
        "error_message_safe": str(result.get("error_message_safe") or "")[:240],
    }


def _build_light_hub_from_snapshot(payload: Any = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = _now_iso()
    snapshot = packet_service.load_snapshot_cache()
    target = _target_from_payload_or_snapshot(payload, snapshot)
    universe = {"type": "current_target", "items": [target], "size": 1}
    library = factor_research.build_factor_library_packet(now=now)
    ledger = factor_research.build_factor_data_ledger_packet(factor_library=library, now=now)
    call_ledger = _local_snapshot_call_ledger(snapshot, now)
    hub = factor_research.build_factor_quant_hub_packet(
        mode="light",
        universe=universe,
        factor_library=library,
        data_ledger=ledger,
        daily_close_packet=_snapshot_value(snapshot, "command_center_daily_close_packet"),
        daily_basic_packet=_snapshot_value(snapshot, "command_center_daily_basic_packet"),
        moneyflow_packet=_snapshot_value(snapshot, "moneyflow_packet"),
        hard_risk_packet=_snapshot_value(snapshot, "hard_risk_packet"),
        limit_emotion_packet=_snapshot_value(snapshot, "limit_emotion_packet"),
        chip_packet=_snapshot_value(snapshot, "chip_packet"),
        a_share_fact_lineage_summary=_snapshot_value(snapshot, "a_share_fact_lineage_summary"),
        next_session_projection_packet=_snapshot_value(snapshot, next_session_projection.PACKET_KEY),
        strategy_execution_packet=_snapshot_value(snapshot, "strategy_packet"),
        decision_packet=_snapshot_value(snapshot, "decision_packet"),
        legacy_quant_packet=_snapshot_value(snapshot, "quant_packet"),
        chokepoint_packet=_snapshot_value(snapshot, "command_center_chokepoint_scan_packet"),
        serenity_packet=serenity_radar.build_serenity_method_radar_packet(now=now),
        now=now,
    )
    hub["cache_source"] = "local_factor_light_pipeline"
    hub["source_snapshot_available"] = bool(snapshot)
    hub["task_call_ledger"] = call_ledger
    hub["tushare_called"] = False
    hub["deepseek_called"] = False
    hub["external_calls_triggered"] = False
    hub["does_not_modify_strategy_action"] = True
    hub["does_not_execute_trades"] = True
    return hub, call_ledger


def run_factor_light_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_factor_light",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
        current_step="factor_light_queued",
        warnings=[
            "light mode 仅读取本地 cache/snapshot，不跑全市场回测。",
            "本地 fallback 不调用 Tushare、DeepSeek、GitHub，也不修改 strategy action。",
        ],
    )
    update_task_status(task["task_id"], status="running", progress=0.25, current_step="reading_local_snapshot_cache")
    try:
        hub, call_ledger = _build_light_hub_from_snapshot(payload)
        update_task_status(task["task_id"], status="running", progress=0.55, current_step="writing_factor_values_parquet", call_ledger=call_ledger)
        storage_result = storage_service.persist_factor_values_from_hub(hub)
        storage_ledger = _factor_values_storage_call_ledger(storage_result, _now_iso())
        combined_ledger = list(call_ledger) + [storage_ledger]
        hub["factor_values_storage"] = storage_result
        hub["storage_call_ledger"] = [storage_ledger]
        hub["task_call_ledger"] = combined_ledger
        hub["call_ledger"] = combined_ledger
        hub["tushare_called"] = False
        hub["deepseek_called"] = False
        hub["external_calls_triggered"] = False
        update_task_status(task["task_id"], status="running", progress=0.8, current_step="writing_factor_quant_hub_cache", call_ledger=combined_ledger)
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="factor_light_completed_from_local_cache",
            call_ledger=combined_ledger,
        ) or task
    except Exception as exc:
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="factor_light_failed",
            error_message_safe=str(exc)[:500],
        ) or task


def _extract_provided_explanation_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in ("provided_explanation", "local_explanation_payload", "mock_deepseek_output", "deepseek_response"):
        if key in payload:
            return payload.get(key)
    return None


def _deepseek_task_payload_summary(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "provided_explanation_payload": _extract_provided_explanation_payload(payload) is not None,
    }
    if isinstance(payload, dict):
        for key in ("ts_code", "ticker", "symbol"):
            if payload.get(key):
                summary[key] = str(payload.get(key))
    return summary


def _deepseek_explanation_call_ledger(now: str, *, sanitized_payload: bool) -> list[dict[str, Any]]:
    return [
        {
            "api": "deepseek_factor_explanation",
            "request_params_safe": {
                "mode": "guarded_prompt_only",
                "provided_explanation_payload": sanitized_payload,
            },
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "provided_payload_sanitized" if sanitized_payload else "not_called",
            "error_message_safe": "",
        }
    ]


def _deepseek_prompt_preview(hub: dict[str, Any]) -> dict[str, Any]:
    prompt = factor_research.build_factor_deepseek_explanation_prompt(hub)
    return {
        "status": "ready_not_sent",
        "allowed_top_level_keys": prompt.get("allowed_top_level_keys") or [],
        "would_enter_deepseek_prompt_if_user_authorizes": bool(prompt.get("enters_deepseek_prompt")),
        "enters_deepseek_prompt": False,
        "does_not_include_full_packet": bool(prompt.get("does_not_include_full_packet")),
        "does_not_include_price_or_position": True,
        "does_not_include_factor_values": True,
    }


def run_factor_deepseek_explanation_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        "run_deepseek_factor_explanation",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=_deepseek_task_payload_summary(payload),
        current_step="deepseek_explanation_queued",
        warnings=[
            "DeepSeek 因子解释任务本轮不调用模型；只准备安全 prompt 或清洗已提供的解释 JSON。",
            "解释输出只允许六个白名单字段，不覆盖因子数值、价格、持仓或 strategy action。",
        ],
    )
    update_task_status(task["task_id"], status="running", progress=0.2, current_step="reading_factor_quant_hub_cache")
    now = _now_iso()
    call_ledger = _deepseek_explanation_call_ledger(now, sanitized_payload=False)
    try:
        hub = dict(read_factor_quant_cache())
        update_task_status(task["task_id"], status="running", progress=0.45, current_step="building_guarded_deepseek_prompt_preview")
        prompt_preview = _deepseek_prompt_preview(hub)
        provided_payload = _extract_provided_explanation_payload(payload)
        if provided_payload is None:
            explanation = {
                "called": False,
                "status": "not_called",
                "payload": None,
                "ignored_keys": [],
                "error_message_safe": "",
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "model_call_status": "not_called",
                "source": "prompt_ready_no_model_call",
            }
            current_step = "deepseek_prompt_ready_without_model_call"
        else:
            explanation = factor_research.sanitize_factor_deepseek_explanation(provided_payload)
            explanation["called"] = False
            explanation["model_call_status"] = "not_called"
            explanation["source"] = "provided_payload_sanitized_no_model_call"
            explanation["allowed_keys_enforced"] = True
            call_ledger = _deepseek_explanation_call_ledger(now, sanitized_payload=True)
            current_step = "deepseek_explanation_sanitized_without_model_call"

        hub["deepseek_explanation_prompt_preview"] = prompt_preview
        hub["deepseek_explanation"] = explanation
        hub["deepseek_called"] = False
        hub["deepseek_model_called"] = False
        hub["deepseek_task_external_calls_triggered"] = False
        hub["deepseek_call_ledger"] = call_ledger
        hub["does_not_modify_strategy_action"] = True
        hub["does_not_modify_next_session_operation_zones"] = True
        hub["does_not_execute_trades"] = True

        update_task_status(task["task_id"], status="running", progress=0.75, current_step="writing_guarded_deepseek_explanation_cache", call_ledger=call_ledger)
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step=current_step,
            call_ledger=call_ledger,
        ) or task
    except Exception as exc:
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_explanation_failed",
            error_message_safe=str(exc)[:500],
            call_ledger=call_ledger,
        ) or task


def create_factor_task(task_type: str, payload: Any = None) -> dict[str, Any]:
    if task_type == "run_factor_light":
        return run_factor_light_task(payload)
    if task_type == "run_deepseek_factor_explanation":
        return run_factor_deepseek_explanation_task(payload)
    return create_task_stub(
        task_type,
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
        current_step="factor_quant_task_stub_created",
    )
