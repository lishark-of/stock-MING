from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from numbers import Number
from typing import Any


DEFAULT_HORIZON_DAYS = 10
HISTORICAL_DAYS = 10
SOURCE_READY = "command_center_projection / packet cache"
SOURCE_FALLBACK = "command_center_projection / 示例路径，待刷新"


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _to_number(value: Any, default: float | None = None) -> float | None:
    if value in [None, ""]:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, Number):
        return float(value)
    if isinstance(value, str):
        text = (
            value.strip()
            .replace(",", "")
            .replace("¥", "")
            .replace("￥", "")
            .replace("%", "")
            .replace("万", "")
        )
        if not text or text in {"暂无", "None", "nan", "--"}:
            return default
        try:
            return float(text)
        except Exception:
            return default
    return default


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _date_text(value: Any = None, now: Any = None) -> str:
    text = _to_text(value)
    if len(text) >= 10:
        return text[:10]
    return _now_iso(now)[:10]


def _clamp_horizon(value: Any) -> int:
    try:
        horizon = int(value)
    except Exception:
        horizon = DEFAULT_HORIZON_DAYS
    return min(10, max(5, horizon))


def _has_payload(*packets: Any) -> bool:
    for packet in packets:
        payload = _as_mapping(packet)
        if payload and not payload.get("is_empty"):
            return True
    return False


def _packet_updated_at(*packets: Any, now: Any = None) -> str:
    for packet in packets:
        payload = _as_mapping(packet)
        text = _to_text(
            payload.get("updated_at")
            or payload.get("timestamp")
            or payload.get("finished_at")
            or payload.get("generated_at")
        )
        if text:
            return text
    return _now_iso(now)


def _status_from_inputs(decision_packet: Any, strategy_packet: Any, live_packet: Any, home_snapshot: Any) -> str:
    snapshot = _as_mapping(home_snapshot)
    if not _has_payload(decision_packet, strategy_packet, live_packet, home_snapshot):
        return "waiting"
    freshness = _as_mapping(snapshot.get("data_freshness"))
    if freshness.get("state") in {"stale", "partial_failed"} or snapshot.get("status") == "cached":
        return "cached"
    for packet in (decision_packet, strategy_packet, live_packet):
        payload = _as_mapping(packet)
        if payload.get("stale") or payload.get("last_success"):
            return "cached"
    return "ready"


def _confidence_text(strategy_packet: Mapping[str, Any]) -> str:
    return _to_text(strategy_packet.get("confidence"), "低")


def _probabilities(decision_packet: Mapping[str, Any], strategy_packet: Mapping[str, Any]) -> tuple[int, int, int]:
    action_text = " ".join(
        [
            _to_text(decision_packet.get("overall_action")),
            _to_text(strategy_packet.get("action")),
            _to_text(decision_packet.get("position_mode")),
        ]
    )
    risk = _to_text(decision_packet.get("risk_level"), "中")
    confidence = _confidence_text(strategy_packet)
    if any(key in action_text for key in ["降风险", "减仓", "卖出", "禁止"]):
        return (15, 35, 50)
    if any(key in action_text for key in ["小幅进攻", "试探", "买入", "加仓"]) and risk != "高":
        return (35 if confidence == "高" else 30, 50, 15 if confidence == "高" else 20)
    if risk == "高":
        return (15, 45, 40)
    return (25, 50, 25)


def _base_value(home_snapshot: Mapping[str, Any], live_packet: Mapping[str, Any]) -> float:
    holding = _as_mapping(home_snapshot.get("holding_action"))
    value = _to_number(holding.get("current_price") or holding.get("cost"))
    if value and value > 0:
        return round(value, 4)
    for key in ("market", "quant", "discipline"):
        section = _as_mapping(live_packet.get(key))
        value = _to_number(section.get("current_price") or section.get("price") or section.get("value"))
        if value and value > 0:
            return round(value, 4)
    return 100.0


def _historical_points(base_value: float, market_bias: str = "", days: int = HISTORICAL_DAYS) -> list[dict]:
    if "偏强" in market_bias:
        start_offset = -3.0
        wiggle = 0.55
    elif "偏弱" in market_bias:
        start_offset = 3.0
        wiggle = -0.65
    else:
        start_offset = -1.1
        wiggle = 0.25
    points = []
    for index, t in enumerate(range(-days, 1)):
        progress = index / days
        wave = ((index % 3) - 1) * wiggle
        value = base_value * (1 + (start_offset * (1 - progress) + wave) / 100)
        points.append({"t": t, "value": round(value, 4)})
    points[-1]["value"] = round(base_value, 4)
    return points


def _path_targets(decision_packet: Mapping[str, Any], strategy_packet: Mapping[str, Any]) -> tuple[float, float, float]:
    action_text = " ".join(
        [
            _to_text(decision_packet.get("overall_action")),
            _to_text(strategy_packet.get("action")),
            _to_text(decision_packet.get("market_bias")),
        ]
    )
    risk = _to_text(decision_packet.get("risk_level"), "中")
    if any(key in action_text for key in ["降风险", "减仓", "卖出", "禁止"]):
        return (2.0, -1.0, -6.0)
    if any(key in action_text for key in ["小幅进攻", "试探", "买入", "加仓", "偏强"]) and risk != "高":
        return (6.0, 2.4, -2.8)
    if risk == "高":
        return (1.5, -1.2, -5.2)
    return (3.6, 1.0, -3.4)


def _curve_points(base_value: float, target_pct: float, horizon_days: int, tone_index: int) -> list[dict]:
    points = []
    for day in range(0, horizon_days + 1):
        progress = day / horizon_days
        eased = 1 - (1 - progress) * (1 - progress)
        wave = 0 if day in {0, horizon_days} else ((day + tone_index) % 3 - 1) * 0.18
        value = base_value * (1 + (target_pct * eased + wave) / 100)
        points.append({"t": day, "value": round(value, 4)})
    points[0]["value"] = round(base_value, 4)
    return points


def _default_path_meta(strategy_packet: Mapping[str, Any]) -> list[dict]:
    paths = _as_list(strategy_packet.get("next_5_10_day_paths") or strategy_packet.get("paths"))
    default = [
        {"name": "乐观路径", "trigger": "市场、量化和纪律至少两项同向转强。", "action": "只允许小额试探。", "risk": "不追高、不满仓。"},
        {"name": "中性路径", "trigger": "信号分歧或缺少新增验证。", "action": "等待或只观察。", "risk": "避免把观察误解为买入。"},
        {"name": "谨慎路径", "trigger": "纪律转弱、回撤扩大或刷新失败。", "action": "降风险。", "risk": "优先保现金、降杠杆。"},
    ]
    result = []
    for index, fallback in enumerate(default):
        raw = _as_mapping(paths[index]) if index < len(paths) else {}
        result.append(
            {
                "name": _to_text(raw.get("name"), fallback["name"]),
                "trigger": _to_text(raw.get("trigger") or raw.get("condition"), fallback["trigger"]),
                "action": _to_text(raw.get("action") or raw.get("advice"), fallback["action"]),
                "risk": _to_text(raw.get("risk") or raw.get("risk_note"), fallback["risk"]),
            }
        )
    return result


def _analysis_market_guidance(analysis_method_packet: Any) -> dict:
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market"), "未知")
    if market == "A股":
        return {
            "market": "A股",
            "basis": "A股资金 / 趋势 / 公告验证",
            "paths": [
                {
                    "trigger": "资金流改善、放量站稳、题材共振，且公告无新增负面。",
                    "risk": "涨跌停、流动性、公告风险、融资融券和龙虎榜均需继续验证。",
                },
                {
                    "trigger": "资金和量价信号分歧，题材热度未形成共振。",
                    "risk": "缺少 Tushare 资金流或公告验证时，只能按待验证路径处理。",
                },
                {
                    "trigger": "资金流出、跌破 MA20/MA60，或出现公告、减持、监管风险。",
                    "risk": "若融资融券或龙虎榜不支持，不扩大仓位，优先降风险。",
                },
            ],
        }
    if market == "美股":
        return {
            "market": "美股",
            "basis": "美股财报 / RS / 行业轮动验证",
            "paths": [
                {
                    "trigger": "财报或指引改善，RS 走强，行业轮动占优并接近或突破 52 周新高。",
                    "risk": "财报窗口、宏观利率、盘前盘后波动和无涨跌停机制都需纳入验证。",
                },
                {
                    "trigger": "RS 与行业信号分歧，财报和宏观变量未给出明确方向。",
                    "risk": "利率、美元和美债压力未解除前，不把横盘误读为买点。",
                },
                {
                    "trigger": "财报不及预期、估值压缩，或利率 / 美元 / 美债压力加大。",
                    "risk": "美股无涨跌停，隔夜跳空风险更高，优先控制单票暴露。",
                },
            ],
        }
    if market == "ETF":
        return {
            "market": "ETF",
            "basis": "ETF 赛道 / 指数 / 流动性验证",
            "paths": [
                {
                    "trigger": "赛道强度确认、跟踪指数趋势向上、成交额充足，且回踩不破。",
                    "risk": "不追高；需复核同类 ETF 重叠、流动性和 QDII / 跨境汇率风险。",
                },
                {
                    "trigger": "赛道强弱分化或回踩未确认，等待跟踪指数与成交额二次验证。",
                    "risk": "持仓重叠和溢价折价未确认前，只观察不叠加配置。",
                },
                {
                    "trigger": "赛道过热、持仓重叠加剧、流动性不足或溢价折价异常。",
                    "risk": "主题轮动失败或指数趋势破位时，优先降低 ETF 暴露。",
                },
            ],
        }
    return {
        "market": market,
        "basis": "市场类型待确认 / 数据待验证",
        "paths": [
            {"trigger": "等待市场类型和基础数据确认。", "risk": "市场类型不明时，不套用 A股 / 美股 / ETF 专属口径。"},
            {"trigger": "信号分歧或数据不足。", "risk": "只保留观察路径，不把示例路径当成交易依据。"},
            {"trigger": "刷新失败或纪律转弱。", "risk": "数据缺口扩大时优先保守处理。"},
        ],
    }


def _merge_path_guidance(paths: list[dict], analysis_method_packet: Any) -> tuple[list[dict], str, str]:
    guidance = _analysis_market_guidance(analysis_method_packet)
    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        path_guidance = guidance["paths"][index] if index < len(guidance["paths"]) else {}
        if path_guidance.get("trigger"):
            item["trigger"] = path_guidance["trigger"]
        if path_guidance.get("risk"):
            item["risk"] = path_guidance["risk"]
            item["risk_note"] = path_guidance["risk"]
        guided_paths.append(item)
    return guided_paths, guidance["market"], guidance["basis"]


def build_projection_packet(
    decision_packet: Any = None,
    strategy_packet: Any = None,
    live_packet: Any = None,
    home_snapshot: Any = None,
    analysis_method_packet: Any = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    base_date: Any = None,
    now: Any = None,
) -> dict:
    decision = _as_mapping(decision_packet)
    strategy = _as_mapping(strategy_packet)
    live = _as_mapping(live_packet)
    snapshot = _as_mapping(home_snapshot)
    horizon = _clamp_horizon(horizon_days)
    updated_at = _packet_updated_at(decision, strategy, live, snapshot, now=now)
    status = _status_from_inputs(decision, strategy, live, snapshot)
    base = _base_value(snapshot, live)
    market_bias = _to_text(decision.get("market_bias") or _as_mapping(snapshot.get("today_action")).get("market_bias"), "未刷新")
    probabilities = _probabilities(decision, strategy)
    targets = _path_targets(decision, strategy)
    path_meta = _default_path_meta(strategy)
    names = ["乐观路径", "中性路径", "谨慎路径"]
    colors = ["#14b8a6", "#2563eb", "#f97316"]
    paths = []
    for index, meta in enumerate(path_meta):
        paths.append(
            {
                "name": meta.get("name") or names[index],
                "probability": probabilities[index],
                "points": _curve_points(base, targets[index], horizon, index),
                "action": meta.get("action") or "只观察。",
                "trigger": meta.get("trigger") or "等待验证。",
                "risk": meta.get("risk") or "不追高、不满仓。",
                "color": colors[index],
            }
        )
    paths, market_type, path_basis = _merge_path_guidance(paths, analysis_method_packet)
    fallback = status == "waiting" or not _has_payload(decision, strategy, live, snapshot)
    note = "示例路径 / 待刷新" if fallback else "基于现有结构化 packet 的条件化路径推演"
    return {
        "status": status,
        "horizon_days": horizon,
        "base_date": _date_text(base_date or updated_at, now=now),
        "historical": _historical_points(base, market_bias),
        "paths": paths,
        "market_type": market_type,
        "path_basis": path_basis,
        "market_method_summary": _to_text(_as_mapping(analysis_method_packet).get("summary"), "分析方法待验证"),
        "source": SOURCE_FALLBACK if fallback else SOURCE_READY,
        "updated_at": updated_at,
        "deepseek_called": False,
        "is_fallback": fallback,
        "note": note,
        "base_value": round(base, 4),
        "unit": "price" if base != 100.0 else "index",
    }


def build_projection_packet_from_state(
    state: Any = None,
    live_packet: Any = None,
    home_snapshot: Any = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    now: Any = None,
) -> dict:
    state_map = _as_mapping(state)
    return build_projection_packet(
        decision_packet=state_map.get("command_center_decision_packet") or state_map.get("command_center_decision_last_success"),
        strategy_packet=state_map.get("strategy_execution_packet") or state_map.get("strategy_execution_last_success"),
        live_packet=live_packet or state_map.get("command_center_live_packet"),
        home_snapshot=home_snapshot or state_map.get("command_center_home_snapshot"),
        analysis_method_packet=state_map.get("command_center_analysis_method_packet"),
        horizon_days=horizon_days,
        now=now,
    )
