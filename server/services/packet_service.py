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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_CACHE_PATH = PROJECT_ROOT / ".stock_ming_cache" / "command_center_latest.json"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")

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


def _next_session_echarts_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_key": "next_session_echarts_payload",
        "schema_version": "next_session_echarts_payload.v1",
        "renderer": "ECharts",
        "source_packet": payload.get("source_packet"),
        "cache_only": True,
        "frontend_computes_trade_action": False,
        "does_not_modify_action": True,
        "does_not_modify_operation_zones": True,
        "requires_button_task_for_refresh": True,
        "series_counts": {
            "historical_points": len(payload.get("historical_points") or []),
            "scenario_series": len(payload.get("scenario_series") or []),
            "reference_lines": len(payload.get("reference_lines") or []),
            "operation_zones": len(payload.get("operation_zones") or []),
        },
        "required_fields": [
            "historical_points",
            "scenario_series",
            "reference_lines",
            "operation_zones",
            "y_axis_range",
        ],
        "guardrails": [
            "GET /api/next-session/cache 不触发 Tushare、DeepSeek 或 GitHub。",
            "React/ECharts 只读渲染 cache payload，不计算或覆盖交易动作。",
            "前端不得修改 strategy action、价格、持仓或 operation_zones。",
        ],
    }


def _attach_next_session_chart_contract(payload: dict[str, Any], source_packet: str | None = None) -> dict[str, Any]:
    payload.setdefault("historical_points", [])
    payload.setdefault("scenario_series", [])
    payload.setdefault("reference_lines", [])
    payload.setdefault("operation_zones", [])
    payload.setdefault("warnings", [])
    if source_packet and not payload.get("source_packet"):
        payload["source_packet"] = source_packet
    if "y_axis_range" not in payload:
        payload["y_axis_range"] = _chart_y_axis_range(payload)
    payload["chart_contract"] = _next_session_echarts_contract(payload)
    return payload


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
    if not model:
        return _attach_next_session_chart_contract({
            "status": "missing",
            "source_packet": next_session_projection.PACKET_KEY,
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": False,
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
        "is_exact_next_session_packet": True,
        "uses_real_daily_close": bool(model.get("uses_real_daily_close") or _summary_of_packet(source).get("available")),
        "historical_source_label": "command_center_next_session_projection_packet.chart_render_model",
        "future_source_label": "scenario_paths",
        "historical_points": _chart_points(model.get("historical_series") or model.get("historical_points") or model.get("daily_close_points") or []),
        "scenario_series": [
            {
                "scenario_key": item.get("scenario_key"),
                "scenario_name": item.get("scenario_name") or item.get("name"),
                "color": item.get("color"),
                "points": _chart_points(item.get("points")),
                "source": "chart_render_model",
            }
            for item in model.get("scenario_series") or []
            if isinstance(item, dict)
        ],
        "reference_lines": _exact_reference_lines_from_model(model),
        "operation_zones": _operation_zone_overlays(model.get("operation_zone_overlays") or model.get("operation_zones") or source.get("operation_zones")),
        "warnings": ["图表只读展示，不修改 strategy action、价格、持仓或 operation_zones。"],
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
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(packet_key)
    except Exception:
        return None
    if packet is None:
        return None
    return _normalize_cached_packet(packet_key, packet, source="sqlite_meta", source_key=packet_key)


def _sqlite_metadata() -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {
            "sqlite_meta_available": False,
            "sqlite_meta_path": _sqlite_path_label(),
            "packet_metadata": [],
            "task_metadata": [],
        }
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH)
        packet_metadata = store.list_packet_metadata()
        task_metadata = store.list_task_metadata()
    except Exception as exc:
        return {
            "sqlite_meta_available": False,
            "sqlite_meta_path": _sqlite_path_label(),
            "packet_metadata": [],
            "task_metadata": [],
            "error_message_safe": str(exc)[:240],
        }
    return {
        "sqlite_meta_available": True,
        "sqlite_meta_path": _sqlite_path_label(),
        "packet_metadata": packet_metadata,
        "task_metadata": task_metadata,
    }


def build_packet_registry_cache() -> dict[str, Any]:
    cached = _read_snapshot_packet("command_center_packet_registry")
    if cached:
        return cached
    packet = json_safe(packet_registry.build_command_center_packet_registry())
    return _normalize_cached_packet("command_center_packet_registry", packet, source="local_builder")


def build_factor_quant_cache() -> dict[str, Any]:
    persisted = _read_persisted_packet("command_center_factor_quant_hub_packet")
    if persisted:
        return persisted
    cached = _read_snapshot_packet("command_center_factor_quant_hub_packet")
    if cached:
        return cached
    now = _now_iso()
    snapshot = load_snapshot_cache()
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
            "github_called": False,
            "deepseek_called": False,
            "tushare_called": False,
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
        return persisted
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
        return cached
    snapshot = load_snapshot_cache()
    legacy_projection = _snapshot_value("command_center_projection_packet", snapshot)
    return _cache_missing_packet(
        next_session_projection.PACKET_KEY,
        "Command Center 3.0 cache API 不触发 Tushare/DeepSeek；当前未发现精确的次日操作图谱 packet 缓存。",
        schema_version=next_session_projection.SCHEMA_VERSION,
        source_snapshot_available=bool(snapshot),
        legacy_projection_cache=_summary_of_packet(legacy_projection) if legacy_projection is not None else {"available": False},
        chart_payload=_legacy_projection_chart_payload(legacy_projection) if legacy_projection is not None else _missing_next_session_chart_payload(),
        does_not_modify_action=True,
        does_not_modify_operation_zones=True,
    )


def build_chokepoint_cache() -> dict[str, Any]:
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
            "deepseek_called": False,
            "tushare_called": False,
            "github_called": False,
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
    persisted_keys = sorted(str(item.get("packet_key")) for item in sqlite_meta.get("packet_metadata", []) if item.get("packet_key"))
    available_keys = sorted(set(PACKET_BUILDERS) | set(snapshot_keys) | set(alias_keys) | set(persisted_keys))
    packet_source_rows = [
        {
            "packet_key": key,
            "read_priority": "snapshot > sqlite_meta > local_builder > missing",
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
        "persisted_packet_keys": persisted_keys,
        "registry_count": len(specs) if isinstance(specs, list) else 0,
        "registry": registry,
        "cache_api_policy": {
            "get_cache_external_calls": False,
            "post_tasks_button_gated": True,
            "does_not_modify_strategy_action": True,
        },
    }
    index["call_ledger"] = packet_index_call_ledger(index)
    return index


def read_packet(packet_key: str) -> dict[str, Any]:
    cached = _read_snapshot_packet(str(packet_key))
    if cached:
        return cached
    persisted = _read_persisted_packet(str(packet_key))
    if persisted:
        return persisted
    builder = PACKET_BUILDERS.get(str(packet_key))
    if builder is None:
        return _cache_missing_packet(
            packet_key,
            "3.0 cache API 尚未发现该 packet 的本地缓存；GET 不会触发外部刷新。",
            source_snapshot_available=bool(load_snapshot_cache()),
        )
    return builder()


def packet_index_call_ledger(index: dict[str, Any]) -> list[dict[str, Any]]:
    sqlite_meta = index.get("sqlite_meta") if isinstance(index.get("sqlite_meta"), dict) else {}
    return [
        {
            "api": "local_packet_registry_cache",
            "source_type": "local_cache_index",
            "call_status": "cache_ready",
            "packet_count": len(index.get("available_cache_keys") or []),
            "snapshot_available": bool(index.get("snapshot_available")),
            "sqlite_meta_available": bool(sqlite_meta.get("sqlite_meta_available")),
            "loaded_at": _now_iso(),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
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
