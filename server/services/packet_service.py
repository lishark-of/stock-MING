from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_packet_registry as packet_registry
import command_center_serenity_method_radar as serenity_radar

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_CACHE_PATH = PROJECT_ROOT / ".stock_ming_cache" / "command_center_latest.json"

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


def _cache_path_label() -> str:
    try:
        return str(SNAPSHOT_CACHE_PATH.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(SNAPSHOT_CACHE_PATH)


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
    if not values:
        return [None, None]
    low = min(values)
    high = max(values)
    padding = max((high - low) * 0.08, high * 0.01, 0.5)
    return [round(low - padding, 4), round(high + padding, 4)]


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
    return payload


def _exact_next_session_chart_payload(packet: Any) -> dict[str, Any]:
    source = packet if isinstance(packet, dict) else {}
    model = source.get("chart_render_model") if isinstance(source.get("chart_render_model"), dict) else {}
    if not model:
        return {
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
        }
    payload = {
        "status": "ready",
        "source_packet": next_session_projection.PACKET_KEY,
        "is_exact_next_session_packet": True,
        "uses_real_daily_close": bool(model.get("uses_real_daily_close") or _summary_of_packet(source).get("available")),
        "historical_source_label": "command_center_next_session_projection_packet.chart_render_model",
        "future_source_label": "scenario_paths",
        "historical_points": _chart_points(model.get("historical_points") or model.get("daily_close_points") or []),
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
        "reference_lines": [
            line
            for line in (
                _reference_line("current_price", "当前价", model.get("current_price_line"), tone="blue"),
                _reference_line("cost_price", "成本线", model.get("cost_line"), tone="orange"),
            )
            if line
        ],
        "operation_zones": model.get("operation_zones") or source.get("operation_zones") or [],
        "warnings": ["图表只读展示，不修改 strategy action、价格、持仓或 operation_zones。"],
    }
    payload["y_axis_range"] = model.get("y_axis_range") or _chart_y_axis_range(payload)
    return payload


def _cache_missing_packet(packet_key: str, summary: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "packet_key": packet_key,
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


def build_packet_registry_cache() -> dict[str, Any]:
    cached = _read_snapshot_packet("command_center_packet_registry")
    if cached:
        return cached
    packet = json_safe(packet_registry.build_command_center_packet_registry())
    return _normalize_cached_packet("command_center_packet_registry", packet, source="local_builder")


def build_factor_quant_cache() -> dict[str, Any]:
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
        return cached
    packet = json_safe(serenity_radar.build_serenity_method_radar_packet(now=_now_iso()))
    return _normalize_cached_packet("command_center_serenity_method_radar_packet", packet, source="local_builder")


def build_next_session_cache() -> dict[str, Any]:
    cached = _read_snapshot_packet(next_session_projection.PACKET_KEY)
    if cached:
        cached.setdefault("chart_payload", _exact_next_session_chart_payload(cached))
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
        chart_payload=_legacy_projection_chart_payload(legacy_projection) if legacy_projection is not None else {
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
        },
        does_not_modify_action=True,
        does_not_modify_operation_zones=True,
    )


def build_chokepoint_cache() -> dict[str, Any]:
    cached = _read_snapshot_packet("command_center_chokepoint_scan_packet")
    if cached:
        cached.setdefault("enters_strategy_action", False)
        cached.setdefault("enters_next_session_projection", False)
        return cached
    snapshot = load_snapshot_cache()
    analysis_method = _snapshot_value("analysis_method_packet", snapshot)
    return _cache_missing_packet(
        "command_center_chokepoint_scan_packet",
        "产业链瓶颈扫描未发现精确 packet 缓存；运行必须由按钮任务触发，GET cache 不调用 DeepSeek。",
        schema_version="chokepoint_scan.cache.v1",
        source_snapshot_available=bool(snapshot),
        legacy_analysis_method_cache=_summary_of_packet(analysis_method) if analysis_method is not None else {"available": False},
        enters_strategy_action=False,
        enters_next_session_projection=False,
    )


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
    return {
        "schema_version": "command_center_3_packet_index.v1",
        "available_cache_keys": sorted(set(PACKET_BUILDERS) | set(snapshot_keys) | set(alias_keys)),
        "snapshot_available": bool(snapshot),
        "snapshot_cache_path": _cache_path_label(),
        "snapshot_available_keys": snapshot_keys,
        "snapshot_alias_keys": alias_keys,
        "registry_count": len(specs) if isinstance(specs, list) else 0,
        "registry": registry,
        "cache_api_policy": {
            "get_cache_external_calls": False,
            "post_tasks_button_gated": True,
            "does_not_modify_strategy_action": True,
        },
    }


def read_packet(packet_key: str) -> dict[str, Any]:
    cached = _read_snapshot_packet(str(packet_key))
    if cached:
        return cached
    builder = PACKET_BUILDERS.get(str(packet_key))
    if builder is None:
        return _cache_missing_packet(
            packet_key,
            "3.0 cache API 尚未发现该 packet 的本地缓存；GET 不会触发外部刷新。",
            source_snapshot_available=bool(load_snapshot_cache()),
        )
    return builder()
