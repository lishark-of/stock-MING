from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import margin_etf_focus_provenance, packet_service, task_service


PACKET_KEY = "command_center_3_market_context_cache"
SCHEMA_VERSION = "market_context_cache.v1"
MARGIN_ETF_REFRESH_TASK_TYPE = "refresh_margin_etf_local_packets"
MARGIN_ETF_REFRESH_PACKET_KEY = "command_center_margin_etf_refresh_receipt"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=100): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "market_context_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _packet_row(packet_key: str, packet: Mapping[str, Any], label: str) -> dict[str, Any]:
    return {
        "packet_key": packet_key,
        "label": label,
        "status": packet.get("status"),
        "status_label": packet.get("status_label"),
        "data_status": packet.get("data_status"),
        "trade_date": packet.get("trade_date"),
        "updated_at": packet.get("updated_at") or packet.get("checked_at"),
        "summary": packet.get("summary") or packet.get("evidence_summary"),
        "decision_chain_state": packet.get("decision_chain_state"),
        "decision_chain_effect": packet.get("decision_chain_effect"),
        "decision_guardrail": packet.get("decision_guardrail"),
        "can_enter_decision_chain": packet.get("can_enter_decision_chain"),
        "external_call_policy": packet.get("external_call_policy"),
        "deepseek_called": packet.get("deepseek_called", False),
    }


def _moneyflow_row(packet: Mapping[str, Any]) -> dict[str, Any]:
    row = _packet_row("moneyflow_packet", packet, "资金流")
    row.update(
        {
            "ticker": packet.get("ticker") or packet.get("target"),
            "flow_state": packet.get("flow_state"),
            "direction": packet.get("direction"),
            "main_net_yi": packet.get("main_net_yi"),
            "five_day_main_net_yi": packet.get("five_day_main_net_yi"),
            "large_net_yi": packet.get("large_net_yi"),
            "small_net_yi": packet.get("small_net_yi"),
        }
    )
    return row


def _margin_row(packet: Mapping[str, Any]) -> dict[str, Any]:
    row = _packet_row("margin_packet", packet, "融资融券")
    row.update(
        {
            "ticker": packet.get("ticker") or packet.get("target"),
            "leverage_state": packet.get("leverage_state"),
            "margin_balance_yi": packet.get("margin_balance_yi"),
            "financing_balance_yi": packet.get("financing_balance_yi"),
            "financing_buy_yi": packet.get("financing_buy_yi"),
            "short_sell_volume": packet.get("short_sell_volume"),
        }
    )
    return row


def _limit_row(packet: Mapping[str, Any]) -> dict[str, Any]:
    row = _packet_row("limit_emotion_packet", packet, "涨跌停情绪")
    row.update(
        {
            "ticker": packet.get("ticker") or packet.get("target"),
            "emotion_state": packet.get("emotion_state"),
            "up_limit": packet.get("up_limit"),
            "down_limit": packet.get("down_limit"),
            "distance_to_up_pct": packet.get("distance_to_up_pct"),
            "distance_to_down_pct": packet.get("distance_to_down_pct"),
            "records_available": packet.get("records_available"),
            "concept_available": packet.get("concept_available"),
        }
    )
    return row


def _dragon_tiger_row(packet: Mapping[str, Any]) -> dict[str, Any]:
    row = _packet_row("dragon_tiger_packet", packet, "龙虎榜")
    row.update(
        {
            "ticker": packet.get("ticker") or packet.get("target"),
            "activity_state": packet.get("activity_state"),
            "net_buy_amount_yi": packet.get("net_buy_amount_yi"),
            "buy_amount_yi": packet.get("buy_amount_yi"),
            "sell_amount_yi": packet.get("sell_amount_yi"),
            "reason": packet.get("reason"),
            "inst_summary": packet.get("inst_summary"),
        }
    )
    return row


def _chip_row(packet: Mapping[str, Any]) -> dict[str, Any]:
    row = _packet_row("chip_packet", packet, "筹码")
    row.update(
        {
            "ticker": packet.get("ticker") or packet.get("target"),
            "pressure_state": packet.get("pressure_state"),
            "winner_rate": packet.get("winner_rate"),
            "weight_avg": packet.get("weight_avg"),
            "cost_5pct": packet.get("cost_5pct"),
            "cost_50pct": packet.get("cost_50pct"),
            "cost_95pct": packet.get("cost_95pct"),
            "current_vs_weight_avg_pct": packet.get("current_vs_weight_avg_pct"),
        }
    )
    return row


def read_market_context_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

    market_packet = _as_dict(snapshot_map.get("market_packet"))
    market_profile = _as_dict(snapshot_map.get("market_profile_evidence"))
    moneyflow_packet = _as_dict(snapshot_map.get("moneyflow_packet"))
    margin_packet = _as_dict(snapshot_map.get("margin_packet"))
    dragon_tiger_packet = _as_dict(snapshot_map.get("dragon_tiger_packet"))
    limit_emotion_packet = _as_dict(snapshot_map.get("limit_emotion_packet"))
    chip_packet = _as_dict(snapshot_map.get("chip_packet"))
    etf_packet = _as_dict(snapshot_map.get("etf_packet"))
    margin_etf_summary = _as_dict(snapshot_map.get("margin_etf_summary"))
    facts_packet = _as_dict(snapshot_map.get("facts_packet"))
    data_freshness = _as_dict(snapshot_map.get("data_freshness"))
    data_coverage = _as_dict(snapshot_map.get("data_coverage"))

    packet_rows = [
        _packet_row("market_packet", market_packet, "市场状态"),
        _packet_row("market_profile_evidence", market_profile, "盘面画像"),
        _moneyflow_row(moneyflow_packet),
        _margin_row(margin_packet),
        _dragon_tiger_row(dragon_tiger_packet),
        _limit_row(limit_emotion_packet),
        _chip_row(chip_packet),
        _packet_row("etf_packet", etf_packet, "ETF/替代方案"),
    ]
    packet_rows = [row for row in packet_rows if any(value not in (None, "", [], {}) for value in row.values())]
    ready_count = sum(1 for row in packet_rows if str(row.get("status") or row.get("data_status") or "").lower() in {"ready", "ok", "available"} or str(row.get("status_label") or "").find("已") >= 0)
    missing_count = sum(1 for row in packet_rows if "missing" in str(row.get("status") or row.get("data_status") or "").lower() or "缺" in str(row.get("status_label") or ""))
    status = "ready" if market_packet or market_profile or packet_rows else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_packet_keys": [
            "market_packet",
            "market_profile_evidence",
            "moneyflow_packet",
            "margin_packet",
            "dragon_tiger_packet",
            "limit_emotion_packet",
            "chip_packet",
            "etf_packet",
            "margin_etf_summary",
            "facts_packet",
            "data_freshness",
            "data_coverage",
        ],
        "summary": market_packet.get("summary")
        or market_profile.get("summary")
        or "市场环境 cache 只读展示；页面打开不会自动刷新行情或资金数据。",
        "trade_date": market_packet.get("trade_date")
        or moneyflow_packet.get("trade_date")
        or margin_packet.get("trade_date")
        or limit_emotion_packet.get("trade_date"),
        "updated_at": market_packet.get("updated_at")
        or market_profile.get("updated_at")
        or moneyflow_packet.get("updated_at")
        or data_freshness.get("last_updated"),
        "market_packet": market_packet,
        "market_profile_evidence": market_profile,
        "packet_rows": packet_rows,
        "moneyflow_packet": moneyflow_packet,
        "margin_packet": margin_packet,
        "dragon_tiger_packet": dragon_tiger_packet,
        "limit_emotion_packet": limit_emotion_packet,
        "chip_packet": chip_packet,
        "etf_packet": etf_packet,
        "margin_etf_summary": margin_etf_summary,
        "facts_packet": facts_packet,
        "data_freshness": data_freshness,
        "data_coverage": data_coverage,
        "concept_strength_top": _as_list(market_packet.get("concept_strength_top")) or _as_list(limit_emotion_packet.get("concept_top5")),
        "limit_records": _as_list(limit_emotion_packet.get("limit_records")),
        "dragon_tiger_inst_rows": _as_list(dragon_tiger_packet.get("inst_rows")),
        "chip_pressure_rows": _as_list(chip_packet.get("chips_top_areas")),
        "counts": {
            "packet_count": len(packet_rows),
            "ready_count": ready_count,
            "missing_count": missing_count,
            "verified_source_count": len(_as_list(market_packet.get("verified_sources"))),
            "missing_source_count": len(_as_list(market_packet.get("missing_sources"))),
            "concept_count": len(_as_list(market_packet.get("concept_strength_top")) or _as_list(limit_emotion_packet.get("concept_top5"))),
            "limit_record_count": len(_as_list(limit_emotion_packet.get("limit_records"))),
            "dragon_tiger_inst_count": len(_as_list(dragon_tiger_packet.get("inst_rows"))),
            "chip_area_count": len(_as_list(chip_packet.get("chips_top_areas"))),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_akshare": True,
            "does_not_call_yfinance": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_refresh_quotes": True,
            "does_not_refresh_moneyflow": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "market_context_is_not_trade_instruction": True,
            "post_task_required_for_refresh": True,
        },
        "call_ledger": [
            {
                "api": "local_market_context_cache",
                "source_snapshot": "command_center_latest.json",
                "row_count": len(packet_rows),
                "call_status": "cache_read" if snapshot else "cache_missing",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "akshare_called": False,
        "yfinance_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/market/cache 只读展示本地市场环境缓存；不会自动刷新行情、资金流或两融数据。",
            "市场环境只进入证据解释和路径置信度说明，不直接生成买卖指令。",
            "本页不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有市场环境缓存；3.0 cache 页不会自动补数据。")
    return _json_safe(packet)


def _packet_status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or packet.get("data_status") or packet.get("cache_state") or "").lower()


def run_margin_etf_local_refresh_task(payload: Any = None) -> dict[str, Any]:
    payload_safe = _safe_value(payload)
    payload_map = payload_safe if isinstance(payload_safe, dict) else {}
    etf_packet = packet_service.read_packet("command_center_etf_packet")
    margin_packet = packet_service.read_packet("command_center_margin_packet")
    target = margin_etf_focus_provenance.strict_target(payload_map.get("target"))
    source_projection = margin_etf_focus_provenance.build_source_projection(
        etf_packet,
        margin_packet,
        target=target,
    )
    source_projection_sha256 = (
        margin_etf_focus_provenance.canonical_digest(source_projection) if source_projection is not None else ""
    )
    source_result_version = (
        f"margin-etf-source:{source_projection_sha256}" if source_projection_sha256 else ""
    )
    scope_material = (
        margin_etf_focus_provenance.build_source_scope_material(
            target=target,
            source_projection_sha256=source_projection_sha256,
        )
        if target and source_projection_sha256
        else {}
    )
    scope_hash = (
        margin_etf_focus_provenance.canonical_digest(scope_material) if scope_material else ""
    )
    call_status = "local_packet_replay_ready" if scope_hash else "degraded_local_packet_provenance_invalid"
    failure_mode = "" if scope_hash else "local_packet_provenance_invalid"
    task_payload = {
        "source": "margin_etf_page_button",
        "mode": "local_packet_replay",
        "requested_packet_keys": list(margin_etf_focus_provenance.REQUESTED_PACKET_KEYS),
        "target": target,
        "source_identity": margin_etf_focus_provenance.SOURCE_IDENTITY if scope_hash else "",
        "source_result_version": source_result_version,
        "source_projection_sha256": source_projection_sha256,
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "degraded_reason": failure_mode,
        "external_sources_allowed": False,
        "provider_refresh_allowed": False,
        "model_call_allowed": False,
        "trade_allowed": False,
    }
    task = task_service.create_task_record(
        MARGIN_ETF_REFRESH_TASK_TYPE,
        output_packet_key=MARGIN_ETF_REFRESH_PACKET_KEY,
        payload=task_payload,
        current_step="margin_etf_local_packet_replay_queued",
        warnings=[
            "ETF/融资本地任务只读取 command_center_etf_packet 和 command_center_margin_packet；不会调用 Tushare、DeepSeek 或 GitHub。",
            "缺少本地 packet 时只返回 degraded 原因；不会自动补数据、不执行真实交易、不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    now = _now_iso()
    ledger = [
        {
            "api": "local_margin_etf_packet_refresh",
            "endpoint": margin_etf_focus_provenance.TASK_ROUTE,
            "task_id": task.get("task_id"),
            "task_type": margin_etf_focus_provenance.TASK_TYPE,
            "output_packet_key": margin_etf_focus_provenance.TASK_OUTPUT_PACKET_KEY,
            "request_params_safe": task_payload,
            "target": target,
            "source_identity": task_payload["source_identity"],
            "source_result_version": source_result_version,
            "source_projection_sha256": source_projection_sha256,
            "scope_hash": scope_hash,
            "scope_hash_short": scope_hash[:12],
            "row_count": len(source_projection.get("etf", {}).get("recommended_etfs", [])) if source_projection else 0,
            "data_date": source_projection.get("etf", {}).get("data_date") if source_projection else "",
            "local_fetched_at": now,
            "call_status": call_status,
            "failure_mode": failure_mode,
            "error_message_safe": "local ETF/margin packet provenance invalid" if failure_mode else "",
            "external": False,
            "external_calls_triggered": False,
            "provider_or_model_calls": False,
            "provider_called": False,
            "model_called": False,
            "worker_called": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "trade_called": False,
            "trading_called": False,
            "broker_called": False,
            "order_called": False,
            "real_trading_enabled": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    current_step = (
        "margin_etf_local_packet_replay_ready_no_external_call"
        if call_status == "local_packet_replay_ready"
        else "margin_etf_local_packet_replay_degraded_missing_packet_no_external_call"
    )
    updated = task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        call_ledger=ledger,
        warning="margin_etf_local_packet_replay_completed_no_external_call",
    ) or task
    updated["payload_safe"] = task_payload
    return updated
