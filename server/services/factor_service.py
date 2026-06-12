from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_serenity_method_radar as serenity_radar
from config import get_deepseek_auto_explain_enabled, get_deepseek_factor_explain_mode
from storage.sqlite_meta import SQLiteMetaStore

from . import model_strategy_service, packet_service, storage_service, tushare_task_service
from .task_service import create_task_record, create_task_stub, update_task_status

SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
DEEPSEEK_FACTOR_PROMPT_VERSION = "factor_deepseek_explanation_prompt.v1"


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
    }


def read_factor_quant_cache() -> dict[str, Any]:
    packet = dict(packet_service.build_factor_quant_cache())
    packet["deepseek_explain_governance"] = _deepseek_explain_governance()
    packet["score_chart_payload"] = _factor_score_chart_payload(packet)
    cache_ledger = _factor_quant_cache_call_ledger(packet, _now_iso())
    existing_ledger = packet.get("call_ledger") if isinstance(packet.get("call_ledger"), list) else []
    packet["cache_call_ledger"] = cache_ledger
    packet["call_ledger"] = cache_ledger + list(existing_ledger)
    cache_warning = "GET /api/factor-quant/cache 只读取本地多因子图谱 cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
    existing_warnings = packet.get("warnings") if isinstance(packet.get("warnings"), list) else []
    packet["warnings"] = [cache_warning] + [item for item in existing_warnings if item != cache_warning]
    return packet


def _deepseek_explain_governance(*, payload: Any = None) -> dict[str, Any]:
    mode = get_deepseek_factor_explain_mode()
    configured_auto = get_deepseek_auto_explain_enabled(default=False)
    payload_auto = bool(payload.get("auto_after_task")) if isinstance(payload, dict) else False
    auto_after_task = mode == "auto_after_task" and configured_auto and payload_auto
    return {
        "mode": mode,
        "auto_after_task": auto_after_task,
        "configured_auto_after_task": configured_auto,
        "payload_auto_after_task_requested": payload_auto,
        "manual_task_allowed": mode != "disabled",
        "disabled": mode == "disabled",
        "model": _deepseek_model_strategy("factor_explain").get("model"),
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "cache_reads_never_call_deepseek": True,
        "react_render_never_calls_deepseek": True,
        "streamlit_render_never_calls_deepseek": True,
        "does_not_override_numeric_values": True,
        "does_not_modify_strategy_action": True,
    }


def _factor_universe_cache_part(hub: dict[str, Any]) -> dict[str, Any]:
    universe = hub.get("universe") if isinstance(hub.get("universe"), dict) else {}
    items = universe.get("items") if isinstance(universe.get("items"), list) else []
    return {
        "universe_type": universe.get("type") or "unknown",
        "items": [str(item) for item in items[:12]],
        "size": universe.get("size") if universe.get("size") is not None else len(items),
    }


def _deepseek_explanation_cache_key(hub: dict[str, Any], *, input_hash: str, model_name: str) -> dict[str, Any]:
    return {
        "module": "factor_quant_hub",
        **_factor_universe_cache_part(hub),
        "ts_code": (_factor_universe_cache_part(hub).get("items") or [""])[0],
        "trade_date": hub.get("trade_date") or hub.get("data_date") or "",
        "input_hash": input_hash,
        "model_name": model_name,
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
    }


def _same_deepseek_cache_key(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _score_items(score: dict[str, Any], key: str) -> list[Any]:
    items = score.get(key)
    return items if isinstance(items, list) else []


def _factor_score_chart_payload(packet: dict[str, Any]) -> dict[str, Any]:
    score = packet.get("score") if isinstance(packet.get("score"), dict) else {}
    buckets = [
        ("support", "支持", "support_factors"),
        ("suppress", "压制", "suppress_factors"),
        ("neutral", "中性", "neutral_factors"),
        ("missing", "缺失", "missing_factors"),
        ("conflict", "冲突", "conflict_factors"),
    ]
    bucket_rows = [
        {
            "bucket_key": bucket_key,
            "bucket_label": label,
            "count": len(_score_items(score, score_key)),
            "source_field": f"score.{score_key}",
        }
        for bucket_key, label, score_key in buckets
    ]
    return {
        "status": "ready" if score else "missing",
        "source_packet": packet.get("packet_key") or "command_center_factor_quant_hub_packet",
        "renderer": "ECharts",
        "chart_type": "factor_score_bucket_bar",
        "bucket_rows": bucket_rows,
        "x_axis_labels": [row["bucket_label"] for row in bucket_rows],
        "series": [
            {
                "name": "因子桶数量",
                "type": "bar",
                "data": [row["count"] for row in bucket_rows],
            }
        ],
        "chart_contract": {
            "contract_key": "factor_quant_score_echarts_payload",
            "schema_version": "factor_quant_score_echarts_payload.v1",
            "renderer": "ECharts",
            "cache_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "frontend_computes_trade_action": False,
            "does_not_modify_action": True,
            "does_not_modify_next_session_projection": True,
            "does_not_modify_operation_zones": True,
            "does_not_modify_factor_score": True,
            "series_counts": {
                "bucket_rows": len(bucket_rows),
                "support": bucket_rows[0]["count"],
                "suppress": bucket_rows[1]["count"],
                "neutral": bucket_rows[2]["count"],
                "missing": bucket_rows[3]["count"],
                "conflict": bucket_rows[4]["count"],
            },
            "guardrails": [
                "GET /api/factor-quant/cache 不触发 Tushare、DeepSeek 或 GitHub。",
                "React/ECharts 只读渲染 score buckets，不计算或覆盖交易动作。",
                "因子图表不执行真实交易，不读取或展示 token/key。",
                "因子图表不得修改 strategy action、次日图谱、operation_zones 或 composite_score。",
            ],
        },
        "warnings": [
            "多因子柱状图只展示 score bucket 数量，不是交易建议。",
            "缺失因子只进入 missing bucket，不得作为 suppress 或卖出理由。",
        ],
    }


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
            **_local_ledger_boundary(),
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
            **_local_ledger_boundary(),
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
        **_local_ledger_boundary(),
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
        trade_calendar_packet=_snapshot_value(snapshot, "command_center_trade_calendar_packet") or _snapshot_value(snapshot, "trade_cal_packet") or _snapshot_value(snapshot, "trade_calendar_packet"),
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
        hub["deepseek_explain_governance"] = _deepseek_explain_governance(payload=payload)
        update_task_status(task["task_id"], status="running", progress=0.8, current_step="writing_factor_quant_hub_cache", call_ledger=combined_ledger)
        SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        auto_task = None
        if hub["deepseek_explain_governance"]["auto_after_task"]:
            universe = hub.get("universe") if isinstance(hub.get("universe"), dict) else {}
            universe_items = universe.get("items") if isinstance(universe.get("items"), list) else []
            auto_task = run_factor_deepseek_explanation_task({
                "trigger": "auto_after_run_light",
                "auto_after_task": True,
                "ts_code": str(universe_items[0]) if universe_items else "",
            })
            latest_hub = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_factor_quant_hub_packet")
            if isinstance(latest_hub, dict):
                hub = latest_hub
            hub.setdefault("deepseek_explain_governance", _deepseek_explain_governance(payload=payload))
            hub["deepseek_explain_governance"]["auto_after_task_queued"] = True
            hub["deepseek_explain_governance"]["auto_after_task_id"] = auto_task.get("task_id")
            SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
        final_warning = ""
        if auto_task:
            final_warning = f"auto_after_task_created:{auto_task.get('task_id')}"
        return update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="factor_light_completed_from_local_cache",
            call_ledger=combined_ledger,
            warning=final_warning or None,
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


def _deepseek_model_strategy(purpose: str = "factor_explain") -> dict[str, Any]:
    return model_strategy_service.build_deepseek_model_strategy_ref(purpose)


def _deepseek_explanation_call_ledger(
    now: str,
    *,
    sanitized_payload: bool,
    input_hash: str = "",
    token_estimate: int = 0,
    output_hash: str = "",
    parse_failed: bool | None = None,
    model_call_status: str = "not_called",
    cache_key: dict[str, Any] | None = None,
    call_status_override: str | None = None,
) -> list[dict[str, Any]]:
    strategy = _deepseek_model_strategy("factor_explain")
    call_status = "not_called"
    if sanitized_payload:
        call_status = "provided_payload_parse_failed" if parse_failed else "provided_payload_sanitized"
    if call_status_override:
        call_status = call_status_override
    governance = _deepseek_explain_governance()
    return [
        {
            "api": "deepseek_factor_explanation",
            "request_params_safe": {
                "mode": governance["mode"],
                "auto_after_task": governance["auto_after_task"],
                "configured_auto_after_task": governance["configured_auto_after_task"],
                "provided_explanation_payload": sanitized_payload,
                "validation_mode": "local_sanitizer_only",
                "model_used": strategy.get("model"),
                "model_purpose": strategy.get("purpose"),
                "model_call_status": model_call_status,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "token_estimate": token_estimate,
                "parse_failed": parse_failed if parse_failed is not None else False,
                "cache_key": cache_key or {},
                "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
                "deepseek_model_strategy": strategy,
            },
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": call_status,
            "error_message_safe": "",
            **_local_ledger_boundary(),
        }
    ]


def _deepseek_prompt_preview(hub: dict[str, Any]) -> dict[str, Any]:
    prompt = factor_research.build_factor_deepseek_explanation_prompt(hub)
    strategy = _deepseek_model_strategy("factor_explain")
    return {
        "status": "ready_not_sent",
        "model_used": strategy.get("model"),
        "deepseek_model_strategy": strategy,
        "input_hash": prompt.get("input_hash"),
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "token_estimate": prompt.get("token_estimate"),
        "allowed_top_level_keys": prompt.get("allowed_top_level_keys") or [],
        "would_enter_deepseek_prompt_if_user_authorizes": bool(prompt.get("enters_deepseek_prompt")),
        "enters_deepseek_prompt": False,
        "does_not_include_full_packet": bool(prompt.get("does_not_include_full_packet")),
        "does_not_include_price_or_position": True,
        "does_not_include_factor_values": True,
    }


def _deepseek_validation_summary(
    *,
    explanation: dict[str, Any],
    prompt_preview: dict[str, Any],
    model_strategy: dict[str, Any],
) -> dict[str, Any]:
    ignored_keys = explanation.get("ignored_keys") if isinstance(explanation.get("ignored_keys"), list) else []
    return {
        "status": explanation.get("status") or "not_called",
        "validation_mode": "local_sanitizer_only",
        "model_used": model_strategy.get("model"),
        "model_purpose": model_strategy.get("purpose"),
        "model_call_status": explanation.get("model_call_status") or "not_called",
        "input_hash": explanation.get("input_hash") or prompt_preview.get("input_hash") or "",
        "output_hash": explanation.get("output_hash") or "",
        "cache_key": explanation.get("cache_key") or {},
        "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
        "explain_governance": _deepseek_explain_governance(),
        "prompt_token_estimate": prompt_preview.get("token_estimate") or 0,
        "output_token_estimate": explanation.get("token_estimate") or 0,
        "parse_failed": bool(explanation.get("parse_failed")),
        "allowed_top_level_keys": prompt_preview.get("allowed_top_level_keys") or [],
        "ignored_key_count": len(ignored_keys),
        "ignored_keys": sorted(str(key) for key in ignored_keys),
        "invalid_output_discarded": bool(explanation.get("parse_failed")),
        "does_not_override_numeric_values": explanation.get("does_not_override_numeric_values") is not False,
        "does_not_output_strategy_action": explanation.get("does_not_output_strategy_action") is not False,
        "does_not_modify_strategy_action": True,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
    }


def run_factor_deepseek_explanation_task(payload: Any = None) -> dict[str, Any]:
    governance = _deepseek_explain_governance(payload=payload)
    task = create_task_record(
        "run_deepseek_factor_explanation",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=_deepseek_task_payload_summary(payload),
        current_step="deepseek_explanation_queued",
        warnings=[
            "DeepSeek 因子解释任务本轮不调用模型；由治理模式控制，只准备安全 prompt 或清洗已提供的解释 JSON。",
            "解释输出只允许六个白名单字段，不覆盖因子数值、价格、持仓或 strategy action。",
            f"DeepSeek explanation mode: {governance['mode']}；auto_after_task={governance['auto_after_task']}。",
        ],
    )
    if governance["disabled"]:
        ledger = _deepseek_explanation_call_ledger(
            _now_iso(),
            sanitized_payload=False,
            model_call_status="disabled",
            call_status_override="disabled_by_governance",
        )
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_explanation_disabled_by_governance",
            error_message_safe="deepseek_factor_explain_disabled",
            call_ledger=ledger,
        ) or task
    update_task_status(task["task_id"], status="running", progress=0.2, current_step="reading_factor_quant_hub_cache")
    now = _now_iso()
    call_ledger = _deepseek_explanation_call_ledger(now, sanitized_payload=False)
    try:
        hub = dict(read_factor_quant_cache())
        update_task_status(task["task_id"], status="running", progress=0.45, current_step="building_guarded_deepseek_prompt_preview")
        prompt_preview = _deepseek_prompt_preview(hub)
        model_strategy = _deepseek_model_strategy("factor_explain")
        input_hash = str(prompt_preview.get("input_hash") or "")
        token_estimate = int(prompt_preview.get("token_estimate") or 0)
        model_used = str(model_strategy.get("model") or "")
        cache_key = _deepseek_explanation_cache_key(hub, input_hash=input_hash, model_name=model_used)
        call_ledger = _deepseek_explanation_call_ledger(
            now,
            sanitized_payload=False,
            input_hash=input_hash,
            token_estimate=token_estimate,
            cache_key=cache_key,
        )
        provided_payload = _extract_provided_explanation_payload(payload)
        existing_key = hub.get("deepseek_explanation_cache_key")
        existing_explanation = hub.get("deepseek_explanation") if isinstance(hub.get("deepseek_explanation"), dict) else {}
        if provided_payload is None and _same_deepseek_cache_key(existing_key, cache_key) and existing_explanation.get("status") in {"success", "parse_failed"}:
            call_ledger = _deepseek_explanation_call_ledger(
                now,
                sanitized_payload=False,
                input_hash=input_hash,
                token_estimate=token_estimate,
                cache_key=cache_key,
                call_status_override="cache_hit_no_duplicate_model_call",
            )
            hub["deepseek_explain_governance"] = governance
            hub["deepseek_explanation_cache_key"] = cache_key
            hub["deepseek_explanation_cache_hit"] = True
            update_task_status(task["task_id"], status="running", progress=0.75, current_step="deepseek_explanation_cache_hit", call_ledger=call_ledger)
            SQLiteMetaStore(SQLITE_META_PATH).write_packet("command_center_factor_quant_hub_packet", hub)
            return update_task_status(
                task["task_id"],
                status="success",
                progress=1.0,
                current_step="deepseek_explanation_cache_hit_no_model_call",
                call_ledger=call_ledger,
            ) or task
        if provided_payload is None:
            explanation = {
                "called": False,
                "status": "not_called",
                "parse_failed": False,
                "payload": None,
                "ignored_keys": [],
                "error_message_safe": "",
                "model_used": model_used,
                "input_hash": input_hash,
                "output_hash": "",
                "token_estimate": 0,
                "does_not_override_numeric_values": True,
                "does_not_output_strategy_action": True,
                "model_call_status": "not_called",
                "source": "prompt_ready_no_model_call",
                "cache_key": cache_key,
                "prompt_version": DEEPSEEK_FACTOR_PROMPT_VERSION,
                "deepseek_model_strategy": model_strategy,
            }
            current_step = "deepseek_prompt_ready_without_model_call"
        else:
            explanation = factor_research.sanitize_factor_deepseek_explanation(provided_payload, model_used=model_used, input_hash=input_hash)
            explanation["called"] = False
            explanation["model_call_status"] = "not_called"
            explanation["source"] = "provided_payload_sanitized_no_model_call"
            explanation["allowed_keys_enforced"] = True
            explanation["deepseek_model_strategy"] = model_strategy
            explanation["cache_key"] = cache_key
            explanation["prompt_version"] = DEEPSEEK_FACTOR_PROMPT_VERSION
            call_ledger = _deepseek_explanation_call_ledger(
                now,
                sanitized_payload=True,
                input_hash=input_hash,
                token_estimate=token_estimate,
                output_hash=str(explanation.get("output_hash") or ""),
                parse_failed=bool(explanation.get("parse_failed")),
                model_call_status=str(explanation.get("model_call_status") or "not_called"),
                cache_key=cache_key,
            )
            current_step = "deepseek_explanation_sanitized_without_model_call"

        hub["deepseek_explain_governance"] = governance
        hub["deepseek_explanation_cache_key"] = cache_key
        hub["deepseek_explanation_cache_hit"] = False
        hub["deepseek_explanation_prompt_preview"] = prompt_preview
        hub["deepseek_explanation"] = explanation
        hub["deepseek_validation_summary"] = _deepseek_validation_summary(
            explanation=explanation,
            prompt_preview=prompt_preview,
            model_strategy=model_strategy,
        )
        hub["deepseek_model_strategy"] = model_strategy
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
    if task_type == "refresh_factor_data":
        return tushare_task_service.run_tushare_refresh_task(
            payload,
            task_type="refresh_factor_data",
            output_packet_key="command_center_factor_quant_hub_packet",
            default_apis=("daily", "daily_basic", "moneyflow"),
        )
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
