from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_packet_registry as packet_registry
import command_center_serenity_method_radar as serenity_radar
from storage.sqlite_meta import SQLiteMetaStore
from . import storage_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_CACHE_PATH = PROJECT_ROOT / ".stock_ming_cache" / "command_center_latest.json"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
MARGIN_ETF_FOCUS_SAFETY_FIELDS = (
    "external",
    "external_calls_triggered",
    "provider_or_model_calls",
    "provider_called",
    "model_called",
    "worker_called",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "trade_called",
    "trading_called",
    "broker_called",
    "order_called",
    "real_trading_enabled",
    "contains_secret",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
)

SNAPSHOT_PACKET_ALIASES = {
    "a_share_fact_lineage_summary": "a_share_fact_lineage_summary",
    "a_share_evidence_packet": "a_share_evidence_packet",
    "command_center_chip_packet": "chip_packet",
    "command_center_decision_packet": "decision_packet",
    "command_center_dragon_tiger_packet": "dragon_tiger_packet",
    "command_center_etf_packet": "etf_packet",
    "command_center_facts_packet": "facts_packet",
    "command_center_hard_risk_packet": "hard_risk_packet",
    "command_center_limit_emotion_packet": "limit_emotion_packet",
    "command_center_margin_packet": "margin_packet",
    "command_center_market_packet": "market_packet",
    "command_center_moneyflow_packet": "moneyflow_packet",
    "command_center_projection_packet": "projection_packet",
    "command_center_quant_packet": "quant_packet",
    "command_center_radar_packet": "radar_packet",
    "command_center_trade_calendar_packet": "trade_cal_packet",
    "decision_packet": "decision_packet",
    "strategy_execution_packet": "strategy_packet",
    "strategy_packet": "strategy_packet",
}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "packet could not be JSON serialized"}


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _cache_path_label() -> str:
    try:
        return str(SNAPSHOT_CACHE_PATH.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(SNAPSHOT_CACHE_PATH)


def _sqlite_path_label() -> str:
    try:
        return str(SQLITE_META_PATH.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(SQLITE_META_PATH)


def load_snapshot_cache() -> dict[str, Any]:
    if not SNAPSHOT_CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(SNAPSHOT_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _snapshot_value(packet_key: str, snapshot: dict[str, Any] | None = None) -> Any:
    cache = snapshot if isinstance(snapshot, dict) else load_snapshot_cache()
    if packet_key in cache:
        return cache.get(packet_key)
    alias = SNAPSHOT_PACKET_ALIASES.get(packet_key)
    if alias:
        return cache.get(alias)
    return None


def _snapshot_source_key(packet_key: str, snapshot: dict[str, Any] | None = None) -> str | None:
    cache = snapshot if isinstance(snapshot, dict) else load_snapshot_cache()
    if packet_key in cache:
        return packet_key
    alias = SNAPSHOT_PACKET_ALIASES.get(packet_key)
    if alias in cache:
        return alias
    return None


def _cache_api_flags(source: str, source_key: str | None = None) -> dict[str, Any]:
    return {
        "cache_source": source,
        "source_cache_key": source_key,
        "snapshot_cache_path": _cache_path_label(),
        "cache_api_loaded_at": _now_iso(),
        "cache_api_external_calls_triggered": False,
        "cache_api_deepseek_called": False,
        "cache_api_tushare_called": False,
        "cache_api_github_called": False,
    }


def _normalize_cached_packet(packet_key: str, packet: Any, *, source: str, source_key: str | None = None) -> dict[str, Any]:
    payload = json_safe(packet)
    if not isinstance(payload, dict):
        payload = {"value": payload}
    if packet_key in {"command_center_etf_packet", "command_center_margin_packet"}:
        payload.pop("margin_etf_focus_binding", None)
        payload["cache_api_explicit_safety_fields"] = sorted(
            field for field in MARGIN_ETF_FOCUS_SAFETY_FIELDS if field in payload
        )
    payload.setdefault("packet_key", packet_key)
    payload.update(_cache_api_flags(source, source_key))
    payload.setdefault("external_calls_triggered", False)
    payload.setdefault("deepseek_called", False)
    payload.setdefault("tushare_called", False)
    payload.setdefault("github_called", False)
    return payload


def _summary_of_packet(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return {"available": packet is not None, "type": type(packet).__name__}
    return {
        "available": True,
        "status": packet.get("status"),
        "packet_key": packet.get("packet_key"),
        "schema_version": packet.get("schema_version"),
        "keys": sorted(str(key) for key in packet.keys())[:20],
    }


def _to_number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _chart_x_from_t(value: Any) -> str:
    number = _to_number(value)
    if number is None:
        return str(value or "")
    if number < 0:
        return f"T{int(number)}"
    if number == 0:
        return "T0"
    return f"T+{int(number)}"


def _chart_point(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    price = _to_number(item.get("price") or item.get("close") or item.get("value"))
    if price is None:
        return None
    t_value = item.get("t", item.get("x"))
    return {
        "x": _chart_x_from_t(t_value),
        "t": t_value,
        "price": round(price, 4),
        "source": item.get("source") or "cache_projection",
        "trigger_condition": item.get("trigger_condition"),
        "risk_note": item.get("risk_note") or item.get("confidence_note"),
        "confidence": item.get("confidence"),
    }


def _chart_points(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [point for item in items if (point := _chart_point(item)) is not None]


def _reference_line(key: str, label: str, value: Any, *, tone: str = "neutral") -> dict[str, Any] | None:
    number = _to_number(value)
    if number is None:
        return None
    return {"key": key, "label": label, "value": round(number, 4), "tone": tone}


def _chart_y_axis_range(payload: dict[str, Any]) -> list[float | None]:
    values: list[float] = []
    for point in payload.get("historical_points") or []:
        number = _to_number(point.get("price"))
        if number is not None:
            values.append(number)
    for series in payload.get("scenario_series") or []:
        for point in series.get("points") or []:
            number = _to_number(point.get("price"))
            if number is not None:
                values.append(number)
    for line in payload.get("reference_lines") or []:
        number = _to_number(line.get("value"))
        if number is not None:
            values.append(number)
    for zone in payload.get("operation_zones") or []:
        if not isinstance(zone, dict):
            continue
        for value in zone.get("price_range") or []:
            number = _to_number(value)
            if number is not None:
                values.append(number)
    if not values:
        return [None, None]
    low = min(values)
    high = max(values)
    padding = max((high - low) * 0.08, high * 0.01, 0.5)
    return [round(low - padding, 4), round(high + padding, 4)]


def _latest_historical_point(payload: dict[str, Any]) -> dict[str, Any]:
    points = [item for item in payload.get("historical_points") or [] if isinstance(item, dict)]
    if not points:
        return {"available": False, "x": None, "price": None, "source": ""}
    latest = points[-1]
    return {
        "available": True,
        "x": latest.get("x"),
        "price": latest.get("price"),
        "source": latest.get("source") or payload.get("historical_source_label") or "",
    }


def _scenario_anchor_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    latest = _latest_historical_point(payload)
    latest_price = _to_number(latest.get("price"))
    rows: list[dict[str, Any]] = []
    for series in payload.get("scenario_series") or []:
        if not isinstance(series, dict):
            continue
        points = [item for item in series.get("points") or [] if isinstance(item, dict)]
        first = points[0] if points else {}
        first_price = _to_number(first.get("price"))
        anchor_delta = None if latest_price is None or first_price is None else round(first_price - latest_price, 4)
        rows.append(
            {
                "scenario_key": series.get("scenario_key") or series.get("scenario_name"),
                "scenario_name": series.get("scenario_name") or series.get("scenario_key"),
                "first_x": first.get("x"),
                "first_price": first_price,
                "latest_close": latest_price,
                "anchor_delta": anchor_delta,
                "anchored_to_latest_close": anchor_delta is not None and abs(anchor_delta) <= 0.01,
                "trigger_condition": series.get("trigger_condition") or first.get("trigger_condition") or "路径仅展示条件，不生成交易动作。",
                "risk_note": series.get("risk_note") or first.get("risk_note") or "情景路径不覆盖 strategy action。",
                "source": series.get("source") or payload.get("future_source_label") or "GET /api/next-session/cache",
            }
        )
    return rows


def _reference_line_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in payload.get("reference_lines") or []:
        if not isinstance(line, dict):
            continue
        rows.append(
            {
                "key": line.get("key"),
                "label": line.get("label"),
                "value": line.get("value"),
                "tone": line.get("tone"),
                "source": line.get("source") or payload.get("source_packet") or "GET /api/next-session/cache",
                "frontend_mutable": False,
            }
        )
    return rows


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _zone_interaction_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for zone in payload.get("operation_zones") or []:
        if not isinstance(zone, dict):
            continue
        rows.append(
            {
                "zone_key": zone.get("zone_key"),
                "zone_name": zone.get("zone_name"),
                "price_range": zone.get("price_range"),
                "action_mode": zone.get("action_mode") or "condition_only",
                "source": zone.get("source") or "chart_payload.operation_zones",
                "click_displays": "guardrail",
                "guardrail": zone.get("guardrail") or "只读区域，不改写 operation_zones 或 strategy action。",
                "frontend_mutable": False,
            }
        )
    return rows


def _interaction_readiness_row(
    key: str,
    label: str,
    status: str,
    *,
    source: str,
    note: str,
    blocker: bool = False,
    frontend_mutable: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "source": source,
        "note": note,
        "blocker": blocker,
        "frontend_mutable": frontend_mutable,
    }


def _next_session_interaction_readiness_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    contract = payload.get("chart_contract") if isinstance(payload.get("chart_contract"), dict) else {}
    interaction = contract.get("interaction_contract") if isinstance(contract.get("interaction_contract"), dict) else {}
    hover_fields = _list_or_empty(interaction.get("hover_displays"))
    required_hover = {"price", "source", "trigger_condition", "risk_note"}
    historical_points = _list_or_empty(payload.get("historical_points"))
    scenario_series = _list_or_empty(payload.get("scenario_series"))
    reference_lines = _list_or_empty(payload.get("reference_lines"))
    operation_zones = _list_or_empty(payload.get("operation_zones"))
    reference_line_rows = _list_or_empty(payload.get("reference_line_rows"))
    zone_interaction_rows = _list_or_empty(payload.get("zone_interaction_rows"))
    position_conflict = payload.get("position_conflict")
    deepseek_status = payload.get("deepseek_status")
    has_drawable_data = bool(historical_points or scenario_series)
    safe_boundaries = (
        contract.get("cache_only") is not False
        and bool(contract.get("external_calls_triggered")) is False
        and bool(contract.get("tushare_called")) is False
        and bool(contract.get("deepseek_called")) is False
        and bool(contract.get("github_called")) is False
        and contract.get("does_not_execute_trades") is not False
        and bool(contract.get("frontend_computes_trade_action")) is False
        and contract.get("does_not_modify_action") is not False
        and contract.get("does_not_modify_operation_zones") is not False
    )
    hover_ready = required_hover.issubset({str(field) for field in hover_fields})
    reference_ready = bool(reference_lines) and bool(reference_line_rows) and all(
        isinstance(row, dict) and row.get("frontend_mutable") is False for row in reference_line_rows
    )
    zone_ready = bool(operation_zones) and bool(zone_interaction_rows) and all(
        isinstance(row, dict) and row.get("frontend_mutable") is False for row in zone_interaction_rows
    )
    rows = [
        _interaction_readiness_row(
            "chart_payload_available",
            "ECharts payload",
            "ready" if payload.get("status") != "missing" else "blocked",
            source=str(payload.get("source_packet") or "GET /api/next-session/cache"),
            note="缓存图谱可用于展示。" if payload.get("status") != "missing" else "没有可绘制的本地图谱 cache。",
            blocker=payload.get("status") == "missing",
        ),
        _interaction_readiness_row(
            "drawable_series",
            "可绘制序列",
            "ready" if has_drawable_data else "blocked",
            source="chart_payload.historical_points/scenario_series",
            note=f"historical={len(historical_points)}, scenario={len(scenario_series)}",
            blocker=not has_drawable_data,
        ),
        _interaction_readiness_row(
            "hover_evidence_contract",
            "hover 证据说明",
            "ready" if hover_ready else "blocked",
            source="chart_contract.interaction_contract.hover_displays",
            note="hover 显示 price/source/trigger_condition/risk_note。" if hover_ready else "hover 字段合同不完整。",
            blocker=not hover_ready,
        ),
        _interaction_readiness_row(
            "scenario_click_drilldown",
            "情景路径点击",
            "ready" if scenario_series and interaction.get("click_path_displays") == "trigger_condition" else "pending",
            source="chart_payload.scenario_series",
            note="点击只展示触发条件，不生成交易动作。" if scenario_series else "暂无情景路径可点选。",
        ),
        _interaction_readiness_row(
            "reference_click_source",
            "参考线来源",
            "ready" if reference_ready and interaction.get("click_reference_displays") == "line_source" else "pending",
            source="chart_payload.reference_line_rows",
            note="参考线来源可展示且前端不可改写。" if reference_ready else "暂无完整参考线来源行。",
            frontend_mutable=not reference_ready,
        ),
        _interaction_readiness_row(
            "zone_click_guardrail",
            "操作区点击边界",
            "ready" if zone_ready and interaction.get("click_zone_displays") == "guardrail" else "pending",
            source="chart_payload.zone_interaction_rows",
            note="点击操作区只显示 guardrail，不改 operation_zones。" if zone_ready else "暂无完整操作区点击说明。",
            frontend_mutable=not zone_ready,
        ),
        _interaction_readiness_row(
            "position_conflict_visibility",
            "持仓冲突可视化",
            "ready" if isinstance(position_conflict, dict) else "pending",
            source="chart_payload.position_conflict",
            note="持仓冲突字段已进入图谱 payload。" if isinstance(position_conflict, dict) else "当前 payload 未携带持仓冲突字段。",
        ),
        _interaction_readiness_row(
            "deepseek_status_visibility",
            "DeepSeek 状态可见",
            "ready" if deepseek_status else "pending",
            source="chart_payload.deepseek_status",
            note=f"DeepSeek 状态为 {deepseek_status or 'missing'}；展示状态不触发模型调用。",
        ),
        _interaction_readiness_row(
            "frontend_read_only_boundary",
            "前端只读边界",
            "ready" if safe_boundaries else "blocked",
            source="chart_contract",
            note="React/ECharts 只渲染 cache，不计算 action、不改价格/持仓/operation_zones。" if safe_boundaries else "图表合同存在外联或改写风险。",
            blocker=not safe_boundaries,
            frontend_mutable=not safe_boundaries,
        ),
        _interaction_readiness_row(
            "legacy_streamlit_parity",
            "legacy signal/capability parity",
            "pending",
            source="docs/command_center_3_long_term_goals.md#LTG-08",
            note="compatibility field: retained signal/capability coverage evidence 仍未完成；当前审计不能称为生产替代完成或旧 UI 对齐完成。",
        ),
    ]
    return rows


def _next_session_interaction_readiness_audit(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _list_or_empty(payload.get("interaction_readiness_rows"))
    blocking_count = len([row for row in rows if isinstance(row, dict) and row.get("blocker") is True and row.get("status") != "ready"])
    pending_count = len([row for row in rows if isinstance(row, dict) and row.get("status") == "pending"])
    ready_count = len([row for row in rows if isinstance(row, dict) and row.get("status") == "ready"])
    if blocking_count:
        status = "interaction_blocked"
    elif pending_count:
        status = "interaction_contract_ready_parity_pending"
    else:
        status = "interaction_ready"
    return {
        "schema_version": "next_session_interaction_readiness.v1",
        "status": status,
        "ready_count": ready_count,
        "pending_count": pending_count,
        "blocking_count": blocking_count,
        "streamlit_parity_complete": False,
        "production_replacement_complete": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_action": True,
        "does_not_modify_operation_zones": True,
        "next_action": "complete retained signal/capability coverage review before calling the ECharts map a full replacement.",
    }


def _chart_maturity_status(payload: dict[str, Any]) -> dict[str, Any]:
    anchor_rows = _scenario_anchor_rows(payload)
    position_conflict = payload.get("position_conflict") if isinstance(payload.get("position_conflict"), dict) else {}
    data_trust = payload.get("data_trust_summary") if isinstance(payload.get("data_trust_summary"), dict) else {}
    deepseek = data_trust.get("deepseek") if isinstance(data_trust.get("deepseek"), dict) else {}
    deepseek_status = str(payload.get("deepseek_status") or deepseek.get("status") or "not_called")
    return {
        "status": "ready" if payload.get("is_exact_next_session_packet") and payload.get("uses_real_daily_close") else "partial",
        "has_real_60d_close": bool(payload.get("uses_real_daily_close")) and len(payload.get("historical_points") or []) >= 1,
        "latest_close_anchor": _latest_historical_point(payload),
        "scenario_anchor_count": len(anchor_rows),
        "scenario_anchored_count": len([row for row in anchor_rows if row.get("anchored_to_latest_close")]),
        "position_conflict": bool(position_conflict.get("has_conflict") or position_conflict.get("conflict_flags")),
        "deepseek_status": deepseek_status,
        "frontend_render_only": True,
        "does_not_modify_action": True,
        "does_not_modify_operation_zones": True,
    }


def _next_session_echarts_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_key": "next_session_echarts_payload",
        "schema_version": "next_session_echarts_payload.v1",
        "renderer": "ECharts",
        "source_packet": payload.get("source_packet"),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "frontend_computes_trade_action": False,
        "does_not_modify_action": True,
        "does_not_modify_operation_zones": True,
        "requires_button_task_for_refresh": True,
        "interaction_contract": {
            "source_endpoint": "GET /api/next-session/cache",
            "hover_displays": ["price", "source", "trigger_condition", "risk_note"],
            "click_path_displays": "trigger_condition",
            "click_zone_displays": "guardrail",
            "click_reference_displays": "line_source",
            "y_axis_dynamic_scale": True,
            "frontend_render_only": True,
            "frontend_must_not_calculate_action": True,
        },
        "series_counts": {
            "historical_points": len(payload.get("historical_points") or []),
            "scenario_series": len(payload.get("scenario_series") or []),
            "reference_lines": len(payload.get("reference_lines") or []),
            "operation_zones": len(payload.get("operation_zones") or []),
            "scenario_anchor_rows": len(payload.get("scenario_anchor_rows") or []),
        },
        "required_fields": [
            "historical_points",
            "scenario_series",
            "reference_lines",
            "operation_zones",
            "y_axis_range",
            "scenario_anchor_rows",
        ],
        "guardrails": [
            "GET /api/next-session/cache 不触发 Tushare、DeepSeek 或 GitHub。",
            "React/ECharts 只读渲染 cache payload，不计算或覆盖交易动作。",
            "前端不得修改 strategy action、价格、持仓或 operation_zones。",
        ],
    }


def _next_session_chart_summary(payload: dict[str, Any]) -> dict[str, Any]:
    contract = payload.get("chart_contract") if isinstance(payload.get("chart_contract"), dict) else {}
    counts = contract.get("series_counts") if isinstance(contract.get("series_counts"), dict) else {}
    interaction_audit = payload.get("interaction_readiness_audit") if isinstance(payload.get("interaction_readiness_audit"), dict) else {}
    has_drawable_data = bool((payload.get("historical_points") or []) or (payload.get("scenario_series") or []))
    return {
        "status": payload.get("status") or ("ready" if has_drawable_data else "missing"),
        "symbol": payload.get("symbol") or payload.get("ts_code") or payload.get("confirmed_symbol"),
        "renderer": contract.get("renderer") or "ECharts",
        "source_packet": contract.get("source_packet") or payload.get("source_packet"),
        "is_exact_next_session_packet": bool(payload.get("is_exact_next_session_packet")),
        "uses_real_daily_close": bool(payload.get("uses_real_daily_close")),
        "has_drawable_data": has_drawable_data,
        "historical_point_count": int(counts.get("historical_points") or len(payload.get("historical_points") or [])),
        "scenario_series_count": int(counts.get("scenario_series") or len(payload.get("scenario_series") or [])),
        "reference_line_count": int(counts.get("reference_lines") or len(payload.get("reference_lines") or [])),
        "operation_zone_count": int(counts.get("operation_zones") or len(payload.get("operation_zones") or [])),
        "frontend_computes_trade_action": bool(contract.get("frontend_computes_trade_action")),
        "does_not_modify_action": contract.get("does_not_modify_action") is not False,
        "does_not_modify_operation_zones": contract.get("does_not_modify_operation_zones") is not False,
        "cache_only": contract.get("cache_only") is not False,
        "external_calls_triggered": bool(contract.get("external_calls_triggered")),
        "tushare_called": bool(contract.get("tushare_called")),
        "deepseek_called": bool(contract.get("deepseek_called")),
        "github_called": bool(contract.get("github_called")),
        "does_not_execute_trades": contract.get("does_not_execute_trades") is not False,
        "maturity_status": (payload.get("chart_maturity") or {}).get("status") if isinstance(payload.get("chart_maturity"), dict) else "partial",
        "scenario_anchored_count": (payload.get("chart_maturity") or {}).get("scenario_anchored_count") if isinstance(payload.get("chart_maturity"), dict) else 0,
        "position_conflict": bool((payload.get("position_conflict") or {}).get("has_conflict") or (payload.get("position_conflict") or {}).get("conflict_flags")) if isinstance(payload.get("position_conflict"), dict) else False,
        "deepseek_status": payload.get("deepseek_status") or "not_called",
        "interaction_readiness_status": interaction_audit.get("status") or "missing",
        "interaction_blocking_count": interaction_audit.get("blocking_count", 0),
        "streamlit_parity_complete": interaction_audit.get("streamlit_parity_complete") is True,
        "production_replacement_complete": interaction_audit.get("production_replacement_complete") is True,
    }


def _attach_next_session_chart_contract(payload: dict[str, Any], source_packet: str | None = None) -> dict[str, Any]:
    payload.setdefault("historical_points", [])
    payload.setdefault("scenario_series", [])
    payload.setdefault("reference_lines", [])
    payload.setdefault("operation_zones", [])
    payload.setdefault("warnings", [])
    payload.setdefault("notices", [])
    if source_packet and not payload.get("source_packet"):
        payload["source_packet"] = source_packet
    if "y_axis_range" not in payload:
        payload["y_axis_range"] = _chart_y_axis_range(payload)
    payload["latest_close_anchor"] = _latest_historical_point(payload)
    payload["scenario_anchor_rows"] = _scenario_anchor_rows(payload)
    payload["reference_line_rows"] = _reference_line_rows(payload)
    payload["zone_interaction_rows"] = _zone_interaction_rows(payload)
    payload["chart_maturity"] = _chart_maturity_status(payload)
    payload["chart_contract"] = _next_session_echarts_contract(payload)
    payload["interaction_readiness_rows"] = _next_session_interaction_readiness_rows(payload)
    payload["interaction_readiness_audit"] = _next_session_interaction_readiness_audit(payload)
    payload["chart_summary"] = _next_session_chart_summary(payload)
    return payload


def _attach_next_session_chart_summary(packet: dict[str, Any]) -> dict[str, Any]:
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), dict) else {}
    packet["chart_summary"] = _next_session_chart_summary(chart)
    return packet


def _missing_next_session_chart_payload() -> dict[str, Any]:
    payload = {
        "status": "missing",
        "source_packet": "none",
        "is_exact_next_session_packet": False,
        "uses_real_daily_close": False,
        "historical_points": [],
        "scenario_series": [],
        "reference_lines": [],
        "operation_zones": [],
        "warnings": ["没有可用于 ECharts 的本地次日图谱缓存。"],
        "y_axis_range": [None, None],
    }
    return _attach_next_session_chart_contract(payload)


def _operation_zone_overlay(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    raw_range = item.get("price_range")
    if not isinstance(raw_range, list) or len(raw_range) < 2:
        return None
    low = _to_number(raw_range[0])
    high = _to_number(raw_range[1])
    if low is None or high is None:
        return None
    lower, upper = sorted((low, high))
    return {
        "zone_key": str(item.get("zone_key") or item.get("key") or item.get("zone_name") or "operation_zone"),
        "zone_name": str(item.get("zone_name") or item.get("label") or item.get("zone_key") or "操作区"),
        "price_range": [round(lower, 4), round(upper, 4)],
        "action_mode": item.get("action_mode") or item.get("action") or "condition_only",
        "tone": item.get("tone") or item.get("risk_level") or "neutral",
        "source": item.get("source") or "chart_render_model.operation_zone_overlays",
        "guardrail": item.get("guardrail") or "前端只读展示，不改写 strategy action 或 operation_zones。",
    }


def _operation_zone_overlays(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [zone for item in items if (zone := _operation_zone_overlay(item)) is not None]


def _exact_reference_lines_from_model(model: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [
        line
        for line in (
            _reference_line("current_price", "当前价", model.get("current_price_line"), tone="blue"),
            _reference_line("cost_price", "成本线", model.get("cost_line"), tone="orange"),
        )
        if line
    ]
    for item in model.get("limit_lines") or []:
        if not isinstance(item, dict):
            continue
        line = _reference_line(
            str(item.get("key") or item.get("label") or "limit_line"),
            str(item.get("label") or "涨跌停参考"),
            item.get("value"),
            tone="red" if "涨" in str(item.get("label") or "") else "green",
        )
        if line:
            lines.append(line)
    for index, value in enumerate(model.get("support_lines") or []):
        line = _reference_line(f"support_{index + 1}", f"支撑 {index + 1}", value, tone="green")
        if line:
            lines.append(line)
    for index, value in enumerate(model.get("resistance_lines") or []):
        line = _reference_line(f"resistance_{index + 1}", f"压力 {index + 1}", value, tone="red")
        if line:
            lines.append(line)
    return lines


def _legacy_projection_chart_payload(projection: Any) -> dict[str, Any]:
    packet = projection if isinstance(projection, dict) else {}
    position = packet.get("position_context") if isinstance(packet.get("position_context"), dict) else {}
    reference_lines = []
    for item in packet.get("reference_lines") or []:
        if not isinstance(item, dict):
            continue
        line = _reference_line(str(item.get("key") or "reference"), str(item.get("label") or item.get("key") or "参考线"), item.get("value"), tone=str(item.get("tone") or "neutral"))
        if line:
            reference_lines.append(line)
    for line in (
        _reference_line("current_price", "当前价", position.get("current_price"), tone="blue"),
        _reference_line("cost_price", "成本线", position.get("cost_price"), tone="orange"),
    ):
        if line and all(existing.get("key") != line["key"] for existing in reference_lines):
            reference_lines.append(line)
    scenario_series = []
    for path in packet.get("paths") or []:
        if not isinstance(path, dict):
            continue
        points = _chart_points(path.get("points"))
        if not points:
            continue
        scenario_series.append(
            {
                "scenario_key": path.get("scenario_key") or path.get("name"),
                "scenario_name": path.get("name") or path.get("scenario_name") or "情景路径",
                "probability": path.get("probability"),
                "color": path.get("color"),
                "points": points,
                "source": path.get("source") or packet.get("future_source"),
                "risk_note": path.get("risk_note") or path.get("risk"),
            }
        )
    payload = {
        "status": "ready" if packet else "missing",
        "source_packet": "projection_packet",
        "source_cache_key": "projection_packet",
        "is_exact_next_session_packet": False,
        "uses_real_daily_close": False,
        "historical_source_label": packet.get("historical_source_label") or "legacy projection historical cache",
        "future_source_label": packet.get("future_source_label") or "legacy scenario projection",
        "base_date": packet.get("base_date"),
        "base_value": packet.get("base_value"),
        "unit": packet.get("unit") or "price",
        "historical_points": _chart_points(packet.get("historical")),
        "scenario_series": scenario_series,
        "reference_lines": reference_lines,
        "operation_zones": [],
        "warnings": [
            "当前图表来自 legacy projection_packet cache，不是精确 command_center_next_session_projection_packet。",
            "历史段未验证为真实 60 日 close；前端不得据此计算交易动作。",
            "图表只读展示，不修改 strategy action、价格、持仓或 operation_zones。",
        ],
    }
    payload["y_axis_range"] = _chart_y_axis_range(payload)
    return _attach_next_session_chart_contract(payload)


def _exact_next_session_chart_payload(packet: Any) -> dict[str, Any]:
    source = packet if isinstance(packet, dict) else {}
    model = source.get("chart_render_model") if isinstance(source.get("chart_render_model"), dict) else {}
    position = source.get("position_context") if isinstance(source.get("position_context"), dict) else {}
    data_trust_summary = source.get("data_trust_summary") if isinstance(source.get("data_trust_summary"), dict) else {}
    deepseek_synthesis = source.get("deepseek_synthesis") if isinstance(source.get("deepseek_synthesis"), dict) else {}
    deepseek_status = deepseek_synthesis.get("status") or (data_trust_summary.get("deepseek", {}) if isinstance(data_trust_summary.get("deepseek"), dict) else {}).get("status") or "not_called"
    if not model:
        return _attach_next_session_chart_contract({
            "status": "missing",
            "source_packet": next_session_projection.PACKET_KEY,
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": False,
            "data_trust_summary": data_trust_summary,
            "position_conflict": {
                "has_conflict": bool(position.get("conflict_flags")),
                "conflict_flags": position.get("conflict_flags") or [],
                "source_packet": position.get("source_packet"),
            },
            "deepseek_status": deepseek_status,
            "historical_points": [],
            "scenario_series": [],
            "reference_lines": [],
            "operation_zones": [],
            "warnings": ["精确次日操作图谱 packet 未提供 chart_render_model。"],
            "y_axis_range": [None, None],
        })
    payload = {
        "status": "ready",
        "source_packet": next_session_projection.PACKET_KEY,
        "symbol": source.get("symbol") or source.get("ts_code") or source.get("confirmed_symbol"),
        "is_exact_next_session_packet": True,
        "uses_real_daily_close": bool(model.get("uses_real_daily_close") or _summary_of_packet(source).get("available")),
        "historical_source_label": "command_center_next_session_projection_packet.chart_render_model",
        "future_source_label": "scenario_paths",
        "data_trust_summary": data_trust_summary,
        "position_conflict": {
            "has_conflict": bool(position.get("conflict_flags")),
            "conflict_flags": position.get("conflict_flags") or [],
            "source_packet": position.get("source_packet"),
        },
        "deepseek_status": deepseek_status,
        "historical_points": _chart_points(model.get("historical_series") or model.get("historical_points") or model.get("daily_close_points") or []),
        "scenario_series": [
            {
                "scenario_key": item.get("scenario_key"),
                "scenario_name": item.get("scenario_name") or item.get("name"),
                "color": item.get("color"),
                "points": _chart_points(item.get("points")),
                "source": "chart_render_model",
                "trigger_condition": item.get("trigger_condition") or item.get("action_timing_note"),
                "risk_note": item.get("risk_note") or item.get("confidence_note"),
            }
            for item in model.get("scenario_series") or []
            if isinstance(item, dict)
        ],
        "reference_lines": _exact_reference_lines_from_model(model),
        "operation_zones": _operation_zone_overlays(model.get("operation_zone_overlays") or model.get("operation_zones") or source.get("operation_zones")),
        "warnings": [],
        "notices": ["图表只读展示，不修改研究结论、价格、持仓或参考区。"],
    }
    payload["y_axis_range"] = model.get("y_axis_range") or _chart_y_axis_range(payload)
    return _attach_next_session_chart_contract(payload)


def _cache_missing_packet(packet_key: str, summary: str, **extra: Any) -> dict[str, Any]:
    packet_key_safe = _safe_text(packet_key, limit=160)
    payload = {
        "packet_key": packet_key_safe,
        "mode": "cache_only",
        "status": "cache_missing",
        "summary": summary,
        "deepseek_called": False,
        "tushare_called": False,
        "github_called": False,
        "external_calls_triggered": False,
        "updated_at": _now_iso(),
    }
    payload.update(_cache_api_flags("cache_missing"))
    payload.update(extra)
    return payload


def _read_snapshot_packet(packet_key: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cache = snapshot if isinstance(snapshot, dict) else load_snapshot_cache()
    source_key = _snapshot_source_key(packet_key, cache)
    if not source_key:
        return None
    return _normalize_cached_packet(packet_key, cache.get(source_key), source="stock_ming_snapshot", source_key=source_key)


def _read_persisted_packet(packet_key: str) -> dict[str, Any] | None:
    if not SQLITE_META_PATH.exists():
        return None
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH, read_only=True).read_packet(packet_key)
    except Exception:
        return None
    if packet is None:
        return None
    return _normalize_cached_packet(packet_key, packet, source="sqlite_meta", source_key=packet_key)


def _is_failed_factor_quant_cache_packet(packet: dict[str, Any] | None) -> bool:
    if not isinstance(packet, dict):
        return False
    status = str(packet.get("status") or "").lower()
    return status in {"failed", "error"} or status.endswith("_failed")


def _factor_quant_failed_cache_summary(packet: dict[str, Any]) -> dict[str, Any]:
    call_ledger = packet.get("call_ledger") if isinstance(packet.get("call_ledger"), list) else []
    warnings = packet.get("warnings") if isinstance(packet.get("warnings"), list) else []
    selected_apis = packet.get("selected_apis") if isinstance(packet.get("selected_apis"), list) else []
    return {
        "available": True,
        "status": _safe_text(packet.get("status"), limit=80),
        "task_type": _safe_text(packet.get("task_type"), limit=120),
        "mode": _safe_text(packet.get("mode"), limit=80),
        "cache_source": _safe_text(packet.get("cache_source"), limit=120),
        "source_cache_key": _safe_text(packet.get("source_cache_key"), limit=120),
        "selected_api_count": len(selected_apis),
        "call_ledger_count": len(call_ledger),
        "warning_count": len(warnings),
        "error_message_safe": _safe_text(packet.get("error") or packet.get("error_message_safe"), limit=240),
        "raw_failed_packet_returned": False,
        "fallback_reason": "failed_factor_quant_cache_packet_does_not_block_cache_only_local_builder",
    }


def _sqlite_metadata() -> dict[str, Any]:
    status = storage_service.sqlite_meta_status()
    packet = dict(status) if isinstance(status, dict) else {}
    packet["sqlite_meta_available"] = packet.get("status") == "ready"
    packet["sqlite_meta_path"] = packet.get("path") or _sqlite_path_label()
    packet.setdefault("packet_metadata", [])
    packet.setdefault("task_metadata", [])
    packet.setdefault("metadata_source_rows", [])
    packet.setdefault("metadata_safe_columns", {})
    packet.setdefault("does_not_return_payload_json", True)
    packet.setdefault("cache_only", True)
    packet.setdefault("external_calls_triggered", False)
    packet.setdefault("tushare_called", False)
    packet.setdefault("deepseek_called", False)
    packet.setdefault("github_called", False)
    return packet


def _storage_catalog_summary() -> dict[str, Any]:
    catalog = storage_service.storage_dataset_catalog()
    rows = catalog.get("dataset_catalog") if isinstance(catalog.get("dataset_catalog"), list) else []
    return {
        "status": catalog.get("status"),
        "mode": catalog.get("mode"),
        "dataset_count": catalog.get("dataset_count", len(rows)),
        "supported_datasets": catalog.get("supported_datasets", []),
        "supported_aliases": catalog.get("supported_aliases", []),
        "dataset_catalog": rows,
        "cache_endpoint": "GET /api/storage/catalog",
        "cache_only": bool(catalog.get("cache_only", True)),
        "external_calls_triggered": bool(catalog.get("external_calls_triggered", False)),
        "tushare_called": bool(catalog.get("tushare_called", False)),
        "deepseek_called": bool(catalog.get("deepseek_called", False)),
        "github_called": bool(catalog.get("github_called", False)),
        "does_not_execute_trades": bool(catalog.get("does_not_execute_trades", True)),
        "does_not_modify_strategy_action": bool(catalog.get("does_not_modify_strategy_action", True)),
    }


def build_packet_registry_cache() -> dict[str, Any]:
    cached = _read_snapshot_packet("command_center_packet_registry")
    if cached:
        return cached
    packet = json_safe(packet_registry.build_command_center_packet_registry())
    return _normalize_cached_packet("command_center_packet_registry", packet, source="local_builder")


def build_factor_quant_cache() -> dict[str, Any]:
    failed_cache_summary: dict[str, Any] | None = None
    persisted = _read_persisted_packet("command_center_factor_quant_hub_packet")
    if persisted:
        if _is_failed_factor_quant_cache_packet(persisted):
            failed_cache_summary = _factor_quant_failed_cache_summary(persisted)
        else:
            return persisted
    snapshot = load_snapshot_cache()
    cached = _read_snapshot_packet("command_center_factor_quant_hub_packet", snapshot)
    if cached:
        if _is_failed_factor_quant_cache_packet(cached):
            failed_cache_summary = failed_cache_summary or _factor_quant_failed_cache_summary(cached)
        else:
            if failed_cache_summary:
                cached["cache_fallback_from_failed_factor_quant_packet"] = True
                cached["failed_factor_quant_cache_summary"] = failed_cache_summary
            return cached
    now = _now_iso()
    library = factor_research.build_factor_library_packet(now=now)
    ledger = factor_research.build_factor_data_ledger_packet(factor_library=library, now=now)
    packet = json_safe(
        factor_research.build_factor_quant_hub_packet(
            mode="cache_only",
            factor_library=library,
            data_ledger=ledger,
            a_share_fact_lineage_summary=_snapshot_value("a_share_fact_lineage_summary", snapshot),
            next_session_projection_packet=_snapshot_value(next_session_projection.PACKET_KEY, snapshot),
            strategy_execution_packet=_snapshot_value("strategy_execution_packet", snapshot),
            decision_packet=_snapshot_value("decision_packet", snapshot),
            legacy_quant_packet=_snapshot_value("command_center_quant_packet", snapshot),
            serenity_packet=serenity_radar.build_serenity_method_radar_packet(now=now),
            now=now,
        )
    )
    packet.update(
        _cache_api_flags(
            "local_builder_with_snapshot_context" if snapshot else "local_builder",
            source_key="command_center_latest.json" if snapshot else None,
        )
    )
    packet.setdefault("external_calls_triggered", False)
    packet.setdefault("deepseek_called", False)
    packet.setdefault("tushare_called", False)
    packet.setdefault("github_called", False)
    packet.setdefault("does_not_execute_trades", True)
    packet.setdefault("does_not_modify_strategy_action", True)
    if failed_cache_summary:
        packet["cache_fallback_from_failed_factor_quant_packet"] = True
        packet["failed_factor_quant_cache_summary"] = failed_cache_summary
    packet["source_snapshot_available"] = bool(snapshot)
    packet["linked_snapshot_keys"] = sorted(
        key
        for key in {
            "a_share_fact_lineage_summary",
            "strategy_packet",
            "decision_packet",
            "quant_packet",
            next_session_projection.PACKET_KEY,
        }
        if key in snapshot
    )
    return packet


def build_serenity_cache() -> dict[str, Any]:
    persisted = _read_persisted_packet("command_center_serenity_method_radar_packet")
    if persisted:
        persisted.setdefault("call_ledger", serenity_cache_call_ledger(persisted))
        persisted.setdefault("warnings", ["GET /api/serenity/cache 只读取本地方法来源基线；不会调用 GitHub、DeepSeek、Tushare 或真实交易接口。"])
        return persisted
    cached = _read_snapshot_packet("command_center_serenity_method_radar_packet")
    if cached:
        cached.setdefault("call_ledger", serenity_cache_call_ledger(cached))
        cached.setdefault("warnings", ["GET /api/serenity/cache 只读取本地方法来源基线；不会调用 GitHub、DeepSeek、Tushare 或真实交易接口。"])
        return cached
    packet = json_safe(serenity_radar.build_serenity_method_radar_packet(now=_now_iso()))
    normalized = _normalize_cached_packet("command_center_serenity_method_radar_packet", packet, source="local_builder")
    normalized["call_ledger"] = serenity_cache_call_ledger(normalized)
    normalized["warnings"] = ["GET /api/serenity/cache 只读取本地方法来源基线；不会调用 GitHub、DeepSeek、Tushare 或真实交易接口。"]
    return normalized


def serenity_cache_call_ledger(packet: dict[str, Any]) -> list[dict[str, Any]]:
    repositories = packet.get("repositories") if isinstance(packet.get("repositories"), list) else []
    return [
        {
            "api": "local_serenity_method_radar_cache",
            "request_params_safe": {
                "packet_key": packet.get("packet_key"),
                "cache_source": packet.get("cache_source"),
                "github_status": packet.get("github_status"),
                "source_type": packet.get("source_type"),
            },
            "row_count": len(repositories),
            "data_date": None,
            "local_fetched_at": _now_iso(),
            "call_status": "cache_read",
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "github_called": False,
            "deepseek_called": False,
            "tushare_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def build_next_session_cache() -> dict[str, Any]:
    persisted = _read_persisted_packet(next_session_projection.PACKET_KEY)
    if persisted:
        if isinstance(persisted.get("chart_payload"), dict):
            persisted["chart_payload"] = _attach_next_session_chart_contract(
                persisted["chart_payload"],
                source_packet=next_session_projection.PACKET_KEY,
            )
        else:
            persisted["chart_payload"] = _exact_next_session_chart_payload(persisted)
        persisted.setdefault("does_not_modify_action", True)
        persisted.setdefault("does_not_modify_operation_zones", True)
        return _attach_next_session_chart_summary(persisted)
    cached = _read_snapshot_packet(next_session_projection.PACKET_KEY)
    if cached:
        if isinstance(cached.get("chart_payload"), dict):
            cached["chart_payload"] = _attach_next_session_chart_contract(
                cached["chart_payload"],
                source_packet=next_session_projection.PACKET_KEY,
            )
        else:
            cached["chart_payload"] = _exact_next_session_chart_payload(cached)
        cached.setdefault("does_not_modify_action", True)
        cached.setdefault("does_not_modify_operation_zones", True)
        return _attach_next_session_chart_summary(cached)
    snapshot = load_snapshot_cache()
    legacy_projection = _snapshot_value("command_center_projection_packet", snapshot)
    return _attach_next_session_chart_summary(_cache_missing_packet(
        next_session_projection.PACKET_KEY,
        "Command Center 3.0 cache API 不触发 Tushare/DeepSeek；当前未发现精确的次日操作图谱 packet 缓存。",
        schema_version="next_session_projection.v1",
        source_snapshot_available=bool(snapshot),
        legacy_projection_cache=_summary_of_packet(legacy_projection) if legacy_projection is not None else {"available": False},
        chart_payload=_legacy_projection_chart_payload(legacy_projection) if legacy_projection is not None else _missing_next_session_chart_payload(),
        does_not_modify_action=True,
        does_not_modify_operation_zones=True,
    ))


def build_chokepoint_cache() -> dict[str, Any]:
    persisted = _read_persisted_packet("command_center_chokepoint_scan_packet")
    if persisted:
        persisted.setdefault("enters_strategy_action", False)
        persisted.setdefault("enters_next_session_projection", False)
        persisted.setdefault("call_ledger", chokepoint_cache_call_ledger(persisted))
        persisted.setdefault("warnings", ["GET /api/chokepoint/cache 只读取本地瓶颈扫描 cache；不会调用 DeepSeek、Tushare、GitHub 或真实交易接口。"])
        return persisted
    cached = _read_snapshot_packet("command_center_chokepoint_scan_packet")
    if cached:
        cached.setdefault("enters_strategy_action", False)
        cached.setdefault("enters_next_session_projection", False)
        cached.setdefault("call_ledger", chokepoint_cache_call_ledger(cached))
        cached.setdefault("warnings", ["GET /api/chokepoint/cache 只读取本地瓶颈扫描 cache；不会调用 DeepSeek、Tushare、GitHub 或真实交易接口。"])
        return cached
    snapshot = load_snapshot_cache()
    analysis_method = _snapshot_value("analysis_method_packet", snapshot)
    packet = _cache_missing_packet(
        "command_center_chokepoint_scan_packet",
        "产业链瓶颈扫描未发现精确 packet 缓存；运行必须由按钮任务触发，GET cache 不调用 DeepSeek。",
        schema_version="chokepoint_scan.cache.v1",
        source_snapshot_available=bool(snapshot),
        legacy_analysis_method_cache=_summary_of_packet(analysis_method) if analysis_method is not None else {"available": False},
        enters_strategy_action=False,
        enters_next_session_projection=False,
    )
    packet["call_ledger"] = chokepoint_cache_call_ledger(packet)
    packet["warnings"] = ["GET /api/chokepoint/cache 只读取本地瓶颈扫描 cache；不会调用 DeepSeek、Tushare、GitHub 或真实交易接口。"]
    return packet


def chokepoint_cache_call_ledger(packet: dict[str, Any]) -> list[dict[str, Any]]:
    legacy = packet.get("legacy_analysis_method_cache") if isinstance(packet.get("legacy_analysis_method_cache"), dict) else {}
    return [
        {
            "api": "local_chokepoint_scan_cache",
            "request_params_safe": {
                "packet_key": packet.get("packet_key"),
                "status": packet.get("status"),
                "cache_source": packet.get("cache_source"),
                "legacy_analysis_method_available": bool(legacy.get("available")),
            },
            "row_count": 1 if legacy.get("available") else 0,
            "data_date": None,
            "local_fetched_at": _now_iso(),
            "call_status": "cache_missing" if packet.get("status") == "cache_missing" else "cache_read",
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "deepseek_called": False,
            "tushare_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


PACKET_BUILDERS = {
    "command_center_packet_registry": build_packet_registry_cache,
    "command_center_factor_quant_hub_packet": build_factor_quant_cache,
    "command_center_serenity_method_radar_packet": build_serenity_cache,
    next_session_projection.PACKET_KEY: build_next_session_cache,
    "command_center_chokepoint_scan_packet": build_chokepoint_cache,
}


def list_packets() -> dict[str, Any]:
    registry = build_packet_registry_cache()
    specs = registry.get("packets") or registry.get("packet_specs") or []
    snapshot = load_snapshot_cache()
    snapshot_keys = sorted(snapshot)
    alias_keys = sorted(api_key for api_key, source_key in SNAPSHOT_PACKET_ALIASES.items() if source_key in snapshot)
    sqlite_meta = _sqlite_metadata()
    storage_catalog = _storage_catalog_summary()
    persisted_keys = sorted(str(item.get("packet_key")) for item in sqlite_meta.get("packet_metadata", []) if item.get("packet_key"))
    available_keys = sorted(set(PACKET_BUILDERS) | set(snapshot_keys) | set(alias_keys) | set(persisted_keys))
    packet_source_rows = [
        {
            "packet_key": key,
            "read_priority": "sqlite_meta > snapshot > local_builder > missing",
            "snapshot": key in snapshot_keys,
            "snapshot_alias": key in alias_keys,
            "sqlite_meta": key in persisted_keys,
            "local_builder": key in PACKET_BUILDERS,
        }
        for key in available_keys
    ]
    index = {
        "schema_version": "command_center_3_packet_index.v1",
        "available_cache_keys": available_keys,
        "packet_source_rows": packet_source_rows,
        "snapshot_available": bool(snapshot),
        "snapshot_cache_path": _cache_path_label(),
        "snapshot_available_keys": snapshot_keys,
        "snapshot_alias_keys": alias_keys,
        "sqlite_meta": sqlite_meta,
        "storage_catalog": storage_catalog,
        "persisted_packet_keys": persisted_keys,
        "registry_count": len(specs) if isinstance(specs, list) else 0,
        "registry": registry,
        "cache_api_policy": {
            "get_cache_external_calls": False,
            "post_tasks_button_gated": True,
            "does_not_modify_strategy_action": True,
            "storage_catalog_cache_endpoint": "GET /api/storage/catalog",
        },
    }
    index["call_ledger"] = packet_index_call_ledger(index)
    return index


def _read_packet_without_margin_etf_binding(packet_key: str) -> dict[str, Any]:
    if packet_key == "command_center_factor_quant_hub_packet":
        return build_factor_quant_cache()
    persisted = _read_persisted_packet(packet_key)
    if persisted:
        return persisted
    cached = _read_snapshot_packet(packet_key)
    if cached:
        return cached
    builder = PACKET_BUILDERS.get(packet_key)
    if builder is None:
        return _cache_missing_packet(
            packet_key,
            "3.0 cache API 尚未发现该 packet 的本地缓存；GET 不会触发外部刷新。",
            source_snapshot_available=bool(load_snapshot_cache()),
        )
    return builder()


def read_packet(packet_key: str) -> dict[str, Any]:
    packet_key_text = str(packet_key)
    packet = _read_packet_without_margin_etf_binding(packet_key_text)
    if packet_key_text not in {"command_center_etf_packet", "command_center_margin_packet"}:
        return packet
    import command_center_home_snapshot as home_snapshot

    etf_packet = (
        packet
        if packet_key_text == "command_center_etf_packet"
        else _read_packet_without_margin_etf_binding("command_center_etf_packet")
    )
    margin_packet = (
        packet
        if packet_key_text == "command_center_margin_packet"
        else _read_packet_without_margin_etf_binding("command_center_margin_packet")
    )
    freshness = load_snapshot_cache().get("data_freshness")
    bound_etf, bound_margin = home_snapshot._attach_margin_etf_focus_binding(
        etf_packet,
        margin_packet,
        freshness,
    )
    return bound_etf if packet_key_text == "command_center_etf_packet" else bound_margin


def packet_index_call_ledger(index: dict[str, Any]) -> list[dict[str, Any]]:
    sqlite_meta = index.get("sqlite_meta") if isinstance(index.get("sqlite_meta"), dict) else {}
    storage_catalog = index.get("storage_catalog") if isinstance(index.get("storage_catalog"), dict) else {}
    return [
        {
            "api": "local_packet_registry_cache",
            "source_type": "local_cache_index",
            "call_status": "cache_ready",
            "read_priority": "sqlite_meta > snapshot > local_builder > missing",
            "packet_count": len(index.get("available_cache_keys") or []),
            "storage_dataset_count": storage_catalog.get("dataset_count", 0),
            "snapshot_available": bool(index.get("snapshot_available")),
            "sqlite_meta_available": bool(sqlite_meta.get("sqlite_meta_available")),
            "sqlite_packet_count": len(sqlite_meta.get("packet_metadata") or []),
            "sqlite_task_count": len(sqlite_meta.get("task_metadata") or []),
            "does_not_return_payload_json": bool(sqlite_meta.get("does_not_return_payload_json", True)),
            "metadata_safe_columns_exposed": bool(sqlite_meta.get("metadata_safe_columns")),
            "loaded_at": _now_iso(),
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def packet_detail_call_ledger(packet: dict[str, Any]) -> list[dict[str, Any]]:
    source = packet.get("cache_source") or packet.get("source_type") or "local_builder"
    status = packet.get("status") or "cache_ready"
    rows: list[dict[str, Any]] = [
        {
            "api": "local_packet_cache_read",
            "packet_key": _safe_text(packet.get("packet_key"), limit=160),
            "cache_source": source,
            "source_cache_key": packet.get("source_cache_key"),
            "read_priority": "sqlite_meta > snapshot > local_builder > missing",
            "source_resolution": source,
            "sqlite_meta_selected": source == "sqlite_meta",
            "snapshot_selected": source == "stock_ming_snapshot",
            "local_builder_selected": str(source).startswith("local_builder"),
            "cache_missing_selected": status == "cache_missing",
            "call_status": "cache_missing" if status == "cache_missing" else "cache_ready",
            "loaded_at": packet.get("cache_api_loaded_at") or _now_iso(),
            "external": False,
            "external_calls_triggered": bool(packet.get("cache_api_external_calls_triggered", packet.get("external_calls_triggered", False))),
            "tushare_called": bool(packet.get("cache_api_tushare_called", packet.get("tushare_called", False))),
            "deepseek_called": bool(packet.get("cache_api_deepseek_called", packet.get("deepseek_called", False))),
            "github_called": bool(packet.get("cache_api_github_called", packet.get("github_called", False))),
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": not bool(packet.get("enters_strategy_action", False)),
        }
    ]
    packet_rows = packet.get("call_ledger") if isinstance(packet.get("call_ledger"), list) else []
    for row in packet_rows:
        if isinstance(row, dict):
            rows.append(json_safe(row))
    return rows
