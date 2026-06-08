from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_data_health_ledger import build_data_health_impact_summary


DEFAULT_HORIZON_DAYS = 10
HISTORICAL_DAYS = 10
SOURCE_READY = "command_center_projection / packet cache"
SOURCE_FALLBACK = "command_center_projection / 示例路径，待刷新"
SOURCE_DEEPSEEK_OVERLAY = "command_center_projection / DeepSeek manual overlay"


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


def _current_price_value(home_snapshot: Mapping[str, Any], live_packet: Mapping[str, Any]) -> float | None:
    holding = _as_mapping(home_snapshot.get("holding_action"))
    value = _to_number(holding.get("current_price"))
    if value and value > 0:
        return round(value, 4)
    for key in ("market", "quant", "discipline"):
        section = _as_mapping(live_packet.get(key))
        value = _to_number(section.get("current_price") or section.get("price") or section.get("value"))
        if value and value > 0:
            return round(value, 4)
    return None


def _base_value(home_snapshot: Mapping[str, Any], live_packet: Mapping[str, Any]) -> float:
    value = _current_price_value(home_snapshot, live_packet)
    if value and value > 0:
        return round(value, 4)
    return 100.0


def _holding_margin_ratio(home_snapshot: Mapping[str, Any]) -> float | None:
    holding = _as_mapping(home_snapshot.get("holding_action"))
    margin_summary = _as_mapping(home_snapshot.get("margin_etf_summary"))
    margin_risk = _as_mapping(_as_mapping(home_snapshot.get("risk_breakdown")).get("margin"))
    value = _to_number(
        holding.get("margin_ratio_pct")
        or holding.get("margin_ratio")
        or margin_summary.get("current_margin_ratio")
        or margin_risk.get("ratio_pct")
    )
    return value if value is not None else None


def _position_projection_context(
    home_snapshot: Mapping[str, Any],
    live_packet: Mapping[str, Any],
    base_value: float,
) -> dict:
    holding = _as_mapping(home_snapshot.get("holding_action"))
    margin_summary = _as_mapping(home_snapshot.get("margin_etf_summary"))
    current_price = _current_price_value(home_snapshot, live_packet)
    cost_price = _to_number(holding.get("cost") or holding.get("cost_price"))
    shares = _to_number(holding.get("shares") or holding.get("holding_units"))
    floating = _as_mapping(holding.get("floating_pnl"))
    pnl_pct = _to_number(floating.get("pct") or holding.get("pnl_pct"))
    pnl_amount = _to_number(floating.get("amount") or holding.get("pnl_amount"))
    if current_price is not None and cost_price and shares:
        if pnl_pct is None:
            pnl_pct = round((current_price / cost_price - 1) * 100, 2)
        if pnl_amount is None:
            pnl_amount = round((current_price - cost_price) * shares, 2)
    margin_ratio = _holding_margin_ratio(home_snapshot)
    recommended_margin_ratio = _to_number(margin_summary.get("recommended_margin_ratio"))
    cost_amount = round(cost_price * shares, 2) if cost_price and shares else None
    market_value = round(current_price * shares, 2) if current_price is not None and shares else None
    price_basis = "real_price" if current_price is not None else "normalized"
    reference_lines = [
        {
            "key": "current_price",
            "label": "当前价基准" if price_basis == "real_price" else "归一化基准",
            "value": round(current_price if current_price is not None else base_value, 4),
            "tone": "blue",
        }
    ]
    if price_basis == "real_price" and cost_price:
        reference_lines.append(
            {
                "key": "cost_line",
                "label": "成本线",
                "value": round(cost_price, 4),
                "tone": "orange" if current_price is None or current_price < cost_price else "green",
            }
        )
    notes = []
    if current_price is None:
        notes.append("当前价未刷新，本轮趋势以 100 归一化基准展示，不能当作实时价格目标。")
    elif cost_price:
        if current_price >= cost_price:
            notes.append("当前价位于成本线上方，重点观察盈利回撤和触发条件。")
        else:
            notes.append("当前为成本线下方持仓，优先控制风险暴露。")
    if margin_ratio and margin_ratio >= 20:
        notes.append(f"融资比例 {margin_ratio:g}%，不建议因为乐观路径额外加杠杆追高。")
    elif margin_ratio and margin_ratio > 0:
        notes.append(f"融资比例 {margin_ratio:g}%，新增融资需等待价格和数据同时确认。")
    return {
        "ticker": _to_text(holding.get("ticker")),
        "name": _to_text(holding.get("name")),
        "investment_horizon": _to_text(holding.get("investment_horizon")),
        "shares": shares,
        "cost_price": cost_price,
        "current_price": current_price,
        "cost_amount": cost_amount,
        "market_value": market_value,
        "floating_pnl_pct": pnl_pct,
        "floating_pnl_amount": pnl_amount,
        "margin_ratio_pct": margin_ratio,
        "recommended_margin_ratio": recommended_margin_ratio,
        "price_basis": price_basis,
        "reference_lines": reference_lines,
        "summary": "｜".join(notes) or "暂无持仓价格上下文；趋势路径仅作条件化观察。",
        "deepseek_called": False,
    }


def _append_sentence(base: Any, addition: str) -> str:
    text = _to_text(base)
    if not addition:
        return text
    if not text:
        return addition
    if addition in text:
        return text
    return f"{text} {addition}"


def _position_path_note(index: int, target_value: float, base_value: float, context: Mapping[str, Any]) -> dict:
    shares = _to_number(context.get("shares"))
    cost = _to_number(context.get("cost_price"))
    current = _to_number(context.get("current_price"))
    margin = _to_number(context.get("margin_ratio_pct")) or 0
    price_basis = _to_text(context.get("price_basis"), "normalized")
    target_change_pct = round((target_value / base_value - 1) * 100, 2) if base_value else 0.0
    target_pnl_pct = None
    target_pnl_amount = None
    if price_basis == "real_price" and cost and shares:
        target_pnl_pct = round((target_value / cost - 1) * 100, 2)
        target_pnl_amount = round((target_value - cost) * shares, 2)
    if price_basis != "real_price":
        action = "价格未刷新，先按归一化路径观察，不把路径点位当成买卖价。"
        risk = "当前价缺失时，必须先刷新行情，再判断成本线、浮盈亏和仓位动作。"
    elif index == 0:
        action = "触发后也只允许按纪律小幅试探。"
        risk = "不追高；先看是否站稳当前价基准和成本线。"
    elif index == 1:
        action = "持仓观察，等待量价、纪律和数据能力同向确认。"
        risk = "横盘不等于买点；成本线附近避免频繁加减。"
    else:
        action = "优先降风险、保现金，必要时降低融资暴露。"
        risk = "若跌破成本线或谨慎路径触发，不能继续把回撤当成正常波动。"
    if margin >= 20:
        risk = _append_sentence(risk, f"当前融资 {margin:g}%，不新增融资追高。")
        if index == 0:
            action = _append_sentence(action, "融资压力未降前，优先现金小额或 ETF 替代。")
    if current is not None and cost:
        if current < cost:
            risk = _append_sentence(risk, "当前仍低于成本线，先控制浮亏暴露。")
        elif target_value < cost:
            risk = _append_sentence(risk, "路径目标跌回成本线下方时，优先执行降风险。")
    return {
        "target_value": round(target_value, 4),
        "target_label": f"{target_value:.2f}" if price_basis == "real_price" else f"归一化 {target_value:.2f}",
        "target_change_pct": target_change_pct,
        "target_pnl_pct": target_pnl_pct,
        "target_pnl_amount": target_pnl_amount,
        "position_action": action,
        "position_risk_note": risk,
    }


def _merge_position_context_into_paths(
    paths: list[dict],
    position_context: Mapping[str, Any],
    base_value: float,
) -> list[dict]:
    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        points = _as_list(item.get("points"))
        last = _as_mapping(points[-1]) if points else {}
        target = _to_number(last.get("value"), base_value) or base_value
        note = _position_path_note(index, target, base_value, position_context)
        item.update(note)
        item["action"] = _append_sentence(item.get("action"), note["position_action"])
        item["risk"] = _append_sentence(item.get("risk") or item.get("risk_note"), note["position_risk_note"])
        item["risk_note"] = item["risk"]
        guided_paths.append(item)
    return guided_paths


def _historical_point_payload(t: int, value: float, source: str, source_label: str, date: Any = "") -> dict:
    item = {
        "t": t,
        "value": round(value, 4),
        "source": source,
        "source_label": source_label,
    }
    date_text = _to_text(date)
    if date_text:
        item["date"] = date_text
    return item


def _historical_close_candidates(home_snapshot: Mapping[str, Any], live_packet: Mapping[str, Any]) -> tuple[list, str, str]:
    sources = [
        (home_snapshot.get("historical_close_points"), home_snapshot.get("historical_close_source"), home_snapshot.get("historical_close_updated_at")),
        (home_snapshot.get("price_history_close"), home_snapshot.get("price_history_source"), home_snapshot.get("price_history_updated_at")),
        (live_packet.get("historical_close_points"), live_packet.get("historical_close_source"), live_packet.get("historical_close_updated_at")),
        (_as_mapping(live_packet.get("market")).get("historical_close_points"), _as_mapping(live_packet.get("market")).get("historical_close_source"), _as_mapping(live_packet.get("market")).get("historical_close_updated_at")),
    ]
    for raw, source, updated_at in sources:
        items = _as_list(raw)
        if len(items) >= 2:
            return items, _to_text(source, "真实日线 close"), _to_text(updated_at)
    return [], "", ""


def _real_historical_points(home_snapshot: Mapping[str, Any], live_packet: Mapping[str, Any], days: int = HISTORICAL_DAYS) -> tuple[list[dict], dict]:
    candidates, source, updated_at = _historical_close_candidates(home_snapshot, live_packet)
    if len(candidates) < 2:
        return [], {}
    rows = []
    for raw in candidates:
        item = _as_mapping(raw)
        value = _to_number(item.get("close") or item.get("value") or item.get("price"))
        if value is None:
            continue
        rows.append(
            {
                "value": value,
                "date": _to_text(item.get("date") or item.get("trade_date") or item.get("asof")),
                "source": _to_text(item.get("source") or source, source or "真实日线 close"),
            }
        )
    if len(rows) < 2:
        return [], {}
    rows = rows[-(days + 1):]
    offset = len(rows) - 1
    points = [
        _historical_point_payload(
            index - offset,
            row["value"],
            "real_daily_close",
            "真实日线 close",
            row.get("date"),
        )
        for index, row in enumerate(rows)
    ]
    lineage = {
        "source": "real_daily_close",
        "label": "真实日线 close",
        "data_source": source or rows[-1].get("source") or "真实行情",
        "uses_real_daily_close": True,
        "is_normalized": False,
        "updated_at": updated_at,
        "summary": f"历史段使用 {source or '真实行情'} close 序列。",
        "gaps": [],
    }
    return points, lineage


def _synthetic_historical_lineage(price_basis: str) -> dict:
    if price_basis == "real_price":
        return {
            "source": "current_price_anchored_synthetic",
            "label": "当前价锚定的模拟历史段",
            "data_source": "本地规则曲线",
            "uses_real_daily_close": False,
            "is_normalized": False,
            "summary": "历史段按当前价锚定生成，用于连接 T0，不是 Tushare 日线 close。",
            "gaps": ["未接入真实日线 close 序列；历史段不是实际历史走势。"],
        }
    return {
        "source": "normalized_synthetic",
        "label": "归一化历史路径",
        "data_source": "本地规则曲线",
        "uses_real_daily_close": False,
        "is_normalized": True,
        "summary": "当前价缺失时使用 100 归一化路径，不代表实际历史价格。",
        "gaps": ["当前价或真实日线 close 缺失；历史段为归一化路径。"],
    }


def _historical_points(
    base_value: float,
    market_bias: str = "",
    days: int = HISTORICAL_DAYS,
    source: str = "current_price_anchored_synthetic",
    source_label: str = "当前价锚定的模拟历史段",
) -> list[dict]:
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
        points.append(_historical_point_payload(t, value, source, source_label))
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


def _clamp_number(value: Any, minimum: float, maximum: float, default: float | None = None) -> float | None:
    number = _to_number(value, default)
    if number is None:
        return default
    return min(maximum, max(minimum, number))


def _bounded_text(value: Any, fallback: str = "", limit: int = 160) -> str:
    text = _to_text(value, fallback)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _find_overlay_path(paths: list, index: int, name: str) -> dict:
    if index < len(paths):
        direct = _as_mapping(paths[index])
        if direct:
            return direct
    name_text = _to_text(name)
    for raw in paths:
        item = _as_mapping(raw)
        item_name = _to_text(item.get("name") or item.get("path_name") or item.get("label"))
        if item_name and (item_name in name_text or name_text in item_name):
            return item
    return {}


def _overlay_probability(overlay: Mapping[str, Any], overlay_path: Mapping[str, Any], index: int, fallback: Any) -> int:
    keys = [
        ("optimistic", "bullish", "乐观"),
        ("neutral", "base", "中性"),
        ("cautious", "bearish", "谨慎"),
    ][index]
    probability_map = _as_mapping(overlay.get("probability") or overlay.get("probabilities"))
    raw = overlay_path.get("probability") or overlay_path.get("prob") or overlay_path.get("weight")
    if raw in [None, ""]:
        raw = next((probability_map.get(key) for key in keys if probability_map.get(key) not in [None, ""]), None)
    value = _clamp_number(raw, 5, 90)
    if value is None:
        value = _clamp_number(fallback, 5, 90, 33)
    return int(round(value or 33))


def _normalize_probabilities(values: list[int]) -> list[int]:
    total = sum(value for value in values if value > 0)
    if total <= 0:
        return [25, 50, 25]
    normalized = [max(5, int(round(value * 100 / total))) for value in values]
    delta = 100 - sum(normalized)
    if normalized:
        target_index = max(range(len(normalized)), key=lambda index: normalized[index])
        normalized[target_index] = max(5, normalized[target_index] + delta)
    return normalized


def _sanitize_overlay_points(
    raw_points: Any,
    *,
    base_value: float,
    horizon_days: int,
) -> list[dict]:
    points = []
    seen = set()
    for raw in _as_list(raw_points):
        item = _as_mapping(raw)
        t_value = item.get("t")
        if t_value in [None, ""]:
            t_value = item.get("day")
        t_number = _to_number(t_value)
        value = _clamp_number(item.get("value") or item.get("price"), base_value * 0.72, base_value * 1.28)
        if t_number is None or value is None:
            continue
        t = int(round(t_number))
        if t < 0 or t > horizon_days or t in seen:
            continue
        seen.add(t)
        points.append({"t": t, "value": round(value, 4)})
    if not points:
        return []
    points.sort(key=lambda item: item["t"])
    if points[0]["t"] != 0:
        points.insert(0, {"t": 0, "value": round(base_value, 4)})
    else:
        points[0]["value"] = round(base_value, 4)
    if points[-1]["t"] < horizon_days:
        points.append({"t": horizon_days, "value": points[-1]["value"]})
    return points


def _overlay_points(
    overlay_path: Mapping[str, Any],
    current_path: Mapping[str, Any],
    *,
    base_value: float,
    horizon_days: int,
    tone_index: int,
) -> list[dict]:
    raw_points = overlay_path.get("points") or overlay_path.get("curve_points") or overlay_path.get("path_points")
    points = _sanitize_overlay_points(raw_points, base_value=base_value, horizon_days=horizon_days)
    if points:
        return points
    target_pct = _clamp_number(
        overlay_path.get("target_pct")
        or overlay_path.get("target_change_pct")
        or overlay_path.get("expected_return_pct"),
        -18,
        18,
    )
    if target_pct is not None:
        return _curve_points(base_value, target_pct, horizon_days, tone_index)
    current_points = _as_list(current_path.get("points"))
    return current_points if current_points else _curve_points(base_value, 0, horizon_days, tone_index)


def build_deepseek_projection_prompt_context(
    *,
    target: Any = "",
    market_type: Any = "",
    position_profile: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    projection_packet: Any = None,
    home_snapshot: Any = None,
    quant_packet: Any = None,
    discipline_packet: Any = None,
) -> dict:
    """Build a compact, serializable context for a manual DeepSeek projection overlay."""
    projection = _as_mapping(projection_packet)
    return {
        "target": _to_text(target),
        "market_type": _to_text(market_type, projection.get("market_type") or "未知"),
        "position_profile": _as_mapping(position_profile),
        "current_price_anchor": projection.get("base_value"),
        "horizon_days": projection.get("horizon_days") or DEFAULT_HORIZON_DAYS,
        "existing_projection": {
            "status": projection.get("status"),
            "base_value": projection.get("base_value"),
            "path_basis": projection.get("path_basis"),
            "paths": projection.get("paths") or [],
            "data_health": projection.get("path_data_health_summary"),
            "a_share_fact": projection.get("path_fact_recovery_summary"),
            "legacy_chain": projection.get("path_legacy_decision_chain_summary"),
        },
        "decision_packet": _as_mapping(decision_packet),
        "strategy_packet": _as_mapping(strategy_packet),
        "live_packet": _as_mapping(live_packet),
        "home_snapshot": _as_mapping(home_snapshot),
        "quant_packet": _as_mapping(quant_packet),
        "discipline_packet": _as_mapping(discipline_packet),
    }


def merge_deepseek_projection_overlay(
    projection_packet: Any,
    overlay_packet: Any = None,
    *,
    now: Any = None,
    model: str = "deepseek-chat",
    raw_text: Any = None,
    token_estimate: Any = None,
) -> dict:
    """Merge a manually-triggered DeepSeek projection overlay into a safe local packet."""
    payload = dict(_as_mapping(projection_packet) or build_projection_packet(now=now))
    overlay = _as_mapping(overlay_packet)
    if not overlay:
        payload["deepseek_overlay_parse_error"] = "DeepSeek 未返回可解析 JSON；保留原始规则推演。"
        return payload

    horizon = _clamp_horizon(payload.get("horizon_days") or DEFAULT_HORIZON_DAYS)
    base_value = _to_number(payload.get("base_value"), 100.0) or 100.0
    raw_overlay_paths = _as_list(overlay.get("paths") or overlay.get("projection_paths") or overlay.get("scenarios"))
    current_paths = [_as_mapping(path) for path in _as_list(payload.get("paths"))[:3]]
    if len(current_paths) < 3:
        current_paths = build_projection_packet(now=now)["paths"]

    probabilities = []
    for index, current_path in enumerate(current_paths[:3]):
        overlay_path = _find_overlay_path(raw_overlay_paths, index, _to_text(current_path.get("name")))
        probabilities.append(_overlay_probability(overlay, overlay_path, index, current_path.get("probability")))
    probabilities = _normalize_probabilities(probabilities)

    enhanced_paths = []
    for index, current_path in enumerate(current_paths[:3]):
        overlay_path = _find_overlay_path(raw_overlay_paths, index, _to_text(current_path.get("name")))
        item = dict(current_path)
        item["probability"] = probabilities[index]
        item["points"] = _overlay_points(
            overlay_path,
            current_path,
            base_value=base_value,
            horizon_days=horizon,
            tone_index=index,
        )
        item["trigger"] = _bounded_text(
            overlay_path.get("trigger") or overlay_path.get("condition") or current_path.get("trigger"),
            "等待价格、量能、量化和交易纪律共同确认。",
            220,
        )
        item["action"] = _bounded_text(
            overlay_path.get("action") or overlay_path.get("suggested_action") or current_path.get("action"),
            "只观察或按纪律小幅试探。",
            180,
        )
        item["risk"] = _bounded_text(
            overlay_path.get("risk") or overlay_path.get("risk_note") or current_path.get("risk"),
            "若价格、公告或纪律转弱，优先降风险。",
            220,
        )
        item["risk_note"] = item["risk"]
        rationale = _bounded_text(
            overlay_path.get("rationale") or overlay_path.get("reason") or overlay_path.get("basis"),
            "",
            220,
        )
        if rationale:
            item["deepseek_rationale"] = rationale
        item["deepseek_enhanced"] = True
        item["deepseek_source"] = "manual_projection_overlay"
        item["source"] = "manual_deepseek_overlay"
        item["source_label"] = "DeepSeek 手动增强路径"
        enhanced_paths.append(item)

    summary = _bounded_text(
        overlay.get("summary") or overlay.get("path_basis") or overlay.get("rationale"),
        "DeepSeek 手动增强：基于当前结构化数据、量化推演和交易纪律整理三路径。",
        240,
    )
    discipline_notes = [
        _bounded_text(item, limit=120)
        for item in _as_list(overlay.get("discipline_notes") or overlay.get("discipline_checks"))
        if _to_text(item)
    ][:5]
    quant_notes = [
        _bounded_text(item, limit=120)
        for item in _as_list(overlay.get("quant_notes") or overlay.get("quant_signals"))
        if _to_text(item)
    ][:5]
    risk_alerts = [
        _bounded_text(item, limit=120)
        for item in _as_list(overlay.get("risk_alerts") or overlay.get("risks"))
        if _to_text(item)
    ][:5]

    payload["paths"] = enhanced_paths
    payload["status"] = "ready" if payload.get("status") in {"waiting", "cached", "ready"} else payload.get("status", "ready")
    payload["horizon_days"] = horizon
    payload["source"] = SOURCE_DEEPSEEK_OVERLAY
    payload["updated_at"] = _now_iso(now)
    payload["deepseek_called"] = True
    payload["deepseek_mode"] = "manual_projection_overlay"
    payload["deepseek_projection_summary"] = summary
    payload["deepseek_projection_notes"] = {
        "discipline_notes": discipline_notes,
        "quant_notes": quant_notes,
        "risk_alerts": risk_alerts,
    }
    payload["deepseek_projection"] = {
        "status": "enhanced",
        "generated_at": payload["updated_at"],
        "model": model,
        "manual_trigger": True,
        "external_call_policy": "manual_button",
        "summary": summary,
        "token_estimate": token_estimate,
        "raw_text_available": bool(_to_text(raw_text)),
    }
    data_lineage = _as_mapping(payload.get("data_lineage"))
    historical_lineage = _as_mapping(data_lineage.get("historical") or payload.get("historical_data_lineage"))
    future_lineage = {
        "source": "manual_deepseek_overlay",
        "label": "DeepSeek 手动增强路径",
        "data_source": "本地规则三路径 + 手动 DeepSeek 解释增强",
        "uses_real_future_price": False,
        "summary": "未来段由本地规则先生成，再由手动 DeepSeek 整理触发条件和路径说明；不代表未来真实价格。",
        "inputs": ["规则情景推演", "策略执行", "今日总决策", "量化推演", "交易纪律", "风险提示"],
        "gaps": ["DeepSeek 只解释和整理路径，不验证摘要外事实。"],
    }
    payload["future_source"] = future_lineage["source"]
    payload["future_source_label"] = future_lineage["label"]
    payload["future_data_lineage"] = future_lineage
    payload["data_lineage"] = {
        "historical": historical_lineage,
        "future": future_lineage,
        "updated_at": payload["updated_at"],
        "summary": f"历史段：{historical_lineage.get('label') or '待确认'}；未来段：{future_lineage['label']}。",
        "gaps": list(dict.fromkeys([*(historical_lineage.get("gaps") or []), *(future_lineage.get("gaps") or [])])),
        "deepseek_called": True,
    }
    payload["lineage_summary"] = payload["data_lineage"]["summary"]
    payload["lineage_gaps"] = payload["data_lineage"]["gaps"]
    payload["path_basis"] = _append_evidence_text(payload.get("path_basis"), f"DeepSeek 手动增强：{summary}")
    payload["note"] = "DeepSeek 手动增强曲线；只整理路径、触发条件和纪律边界，不自动交易。"
    payload["is_fallback"] = False
    return payload


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


def _evidence_labels(items: Any, limit: int = 3) -> list[str]:
    labels = []
    for item in _as_list(items):
        payload = _as_mapping(item)
        label = _to_text(payload.get("label") or payload.get("key"))
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _evidence_label_text(items: Any, fallback: str = "暂无") -> str:
    labels = _evidence_labels(items)
    return "、".join(labels) if labels else fallback


def _first_evidence_item(evidence: Mapping[str, Any], key: str) -> tuple[str, dict]:
    state_sources = [
        ("supporting", evidence.get("support_items")),
        ("blocked", evidence.get("blocker_items")),
        ("cached", evidence.get("cached_items")),
        ("missing", evidence.get("missing_items")),
    ]
    for state, raw_items in state_sources:
        for item in _as_list(raw_items):
            payload = _as_mapping(item)
            if _to_text(payload.get("key")) == key:
                return state, payload
    return "", {}


def _evidence_item_brief(item: Mapping[str, Any], fallback: str) -> str:
    return _to_text(
        item.get("headline")
        or item.get("metric")
        or item.get("status_label")
        or item.get("evidence_label")
        or item.get("label"),
        fallback,
    )


def _legacy_a_share_path_evidence_notes(evidence: Mapping[str, Any]) -> dict:
    configs = {
        "limit_emotion": {
            "label": "涨跌停/情绪",
            "supporting": "已回流，乐观路径仍需避开追高和涨跌停情绪边界",
            "blocked": "仍受限，不能确认题材温度、追高边界或涨跌停风险",
            "cached": "使用缓存，需复核交易日后再判断情绪边界",
            "missing": "待验证，乐观路径不能假设情绪支持",
            "risk": "涨跌停/情绪只验证短线热度和追高边界，不等于自动加仓。",
        },
        "chip_radar": {
            "label": "筹码/胜率",
            "supporting": "已回流，路径需同时复核压力位、获利盘和胜率口径",
            "blocked": "仍受限，不能确认筹码压力、获利盘或历史胜率",
            "cached": "使用缓存，需复核筹码区间和胜率更新时间",
            "missing": "待验证，不能把压力位或胜率写成已验证依据",
            "risk": "筹码/胜率只验证压力和纪律口径，不替代价格触发条件。",
        },
    }
    support_notes = []
    pending_notes = []
    risk_notes = []
    visible_items = []
    for key, config in configs.items():
        state, item = _first_evidence_item(evidence, key)
        if not state:
            continue
        label = config["label"]
        brief = _evidence_item_brief(item, label)
        note = f"{label}{config.get(state, '待验证')}：{brief}"
        visible_items.append(
            {
                "key": key,
                "label": label,
                "state": state,
                "state_label": _to_text(item.get("evidence_label") or item.get("status_label"), "待验证"),
                "summary": note,
                "deepseek_called": False,
            }
        )
        if state == "supporting":
            support_notes.append(note)
            risk_notes.append(config["risk"])
        else:
            pending_notes.append(note)
            risk_notes.append(config["risk"])
    return {
        "support_text": "；".join(support_notes),
        "pending_text": "；".join(pending_notes),
        "risk_text": "；".join(risk_notes),
        "items": visible_items,
        "deepseek_called": False,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _legacy_decision_chain_guidance(legacy_summary: Any = None) -> dict:
    summary = _as_mapping(legacy_summary)
    if not summary:
        return {}
    items = [_as_mapping(item) for item in _as_list(summary.get("priority_items") or summary.get("items")) if _as_mapping(item)]
    blocked = [item for item in items if _to_text(item.get("decision_chain_state")) == "blocked"]
    cache_only = [item for item in items if _to_text(item.get("decision_chain_state")) == "cache_only"]
    waiting = [item for item in items if _to_text(item.get("decision_chain_state")) == "waiting"]
    ready = [item for item in items if _to_text(item.get("decision_chain_state")) == "ready"]
    status = _to_text(summary.get("status"), "waiting")
    return {
        "status": status,
        "label": _to_text(summary.get("headline") or summary.get("title"), "旧能力决策链"),
        "summary": _to_text(summary.get("summary"), "旧能力决策链待验证"),
        "blocked_text": _limited_join([_to_text(item.get("label")) for item in blocked], fallback="旧能力阻断项", limit=3),
        "cache_text": _limited_join([_to_text(item.get("label")) for item in cache_only], fallback="旧能力缓存项", limit=3),
        "waiting_text": _limited_join([_to_text(item.get("label")) for item in waiting], fallback="旧能力待验证项", limit=3),
        "ready_text": _limited_join([_to_text(item.get("label")) for item in ready], fallback="旧能力已验证项", limit=3),
        "items": items[:6],
        "deepseek_called": False,
    }


def _merge_legacy_decision_chain_guidance(paths: list[dict], legacy_summary: Any = None) -> tuple[list[dict], str, dict]:
    guidance = _legacy_decision_chain_guidance(legacy_summary)
    if not guidance:
        return paths, "", {}
    guided_paths = []
    status = guidance["status"]
    for index, path in enumerate(paths):
        item = dict(path)
        if status == "blocked":
            if index == 0:
                note = f"旧能力阻断压制乐观路径：{guidance['blocked_text']}。"
                risk = f"旧能力阻断未解除前（{guidance['blocked_text']}），不能把乐观路径当作加仓、追高或加融资依据。"
            elif index == 1:
                note = f"中性路径复核旧能力链：{guidance['summary']}。"
                risk = "旧能力阻断存在时，中性路径也只允许观察和等待补证。"
            else:
                note = f"旧能力阻断触发谨慎边界：{guidance['blocked_text']}。"
                risk = f"优先保现金、降风险，并按高级工具箱手动恢复对应 packet：{guidance['blocked_text']}。"
            item["legacy_decision_chain_label"] = "旧能力阻断"
        elif status in {"cache_only", "partial"}:
            if index == 0:
                note = f"旧能力缓存/待验证限制乐观路径：{guidance['cache_text']}；{guidance['waiting_text']}。"
                risk = "缓存和待验证旧能力只能辅助判断，执行前必须复核日期、来源和覆盖口径。"
            elif index == 1:
                note = f"中性路径等待旧能力补证：{guidance['summary']}。"
                risk = "旧能力未完全回流时，保持等待或只观察，不放大仓位。"
            else:
                note = f"若缓存旧能力转弱或补证失败，谨慎路径优先：{guidance['cache_text']}。"
                risk = "缓存过期或补证失败时，优先降低暴露。"
            item["legacy_decision_chain_label"] = "旧能力待复核"
        elif status == "ready":
            note = f"旧能力链已验证，可辅助路径判断：{guidance['ready_text']}。"
            risk = "旧能力已验证也不等于自动交易，仍需价格、纪律和仓位共同确认。"
            item["legacy_decision_chain_label"] = "旧能力可参考"
        else:
            note = "旧能力链待验证，趋势路径只能保留示例和安全空态。"
            risk = "旧能力未回流前，不把趋势路径写成交易依据。"
            item["legacy_decision_chain_label"] = "旧能力待验证"
        item["trigger"] = _append_evidence_text(item.get("trigger"), note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        guided_paths.append(item)
    return guided_paths, f"旧能力链：{guidance['summary']}", guidance


def _limited_join(values: Any, fallback: str = "暂无", limit: int = 2) -> str:
    if isinstance(values, (list, tuple, set)):
        labels = [_to_text(item) for item in values]
    else:
        text = _to_text(values)
        labels = [text] if text else []
    labels = [item for item in labels if item]
    if not labels:
        return fallback
    suffix = f" 等 {len(labels)} 项" if len(labels) > limit else ""
    return "、".join(labels[:limit]) + suffix


def _append_evidence_text(base: Any, addition: str) -> str:
    text = _to_text(base)
    note = _to_text(addition)
    if not note:
        return text
    if not text:
        return note
    return f"{text.rstrip('。；; ')}；{note}"


def _evidence_group_count(group: Mapping[str, Any]) -> int:
    try:
        return max(0, int(float(group.get("count"))))
    except Exception:
        return len([item for item in _as_list(group.get("items")) if _as_mapping(item)])


def _fallback_evidence_status_groups(evidence_radar_packet: Mapping[str, Any]) -> list[dict]:
    configs = [
        ("recovered", "已回流", "ready", evidence_radar_packet.get("support_items")),
        ("blocked", "仍受限", "failed", evidence_radar_packet.get("blocker_items")),
        ("cached", "使用缓存", "stale", evidence_radar_packet.get("cached_items")),
        ("manual", "待手动", "missing", evidence_radar_packet.get("missing_items")),
    ]
    groups = []
    for key, label, tone, raw_items in configs:
        items = [_as_mapping(item) for item in _as_list(raw_items) if _as_mapping(item)]
        groups.append(
            {
                "key": key,
                "label": label,
                "tone": tone,
                "count": len(items),
                "labels_text": _evidence_label_text(items, fallback="无"),
                "deepseek_called": False,
            }
        )
    return groups


def _evidence_status_group_summary(evidence_radar_packet: Mapping[str, Any]) -> dict:
    groups = [_as_mapping(item) for item in _as_list(evidence_radar_packet.get("evidence_status_groups")) if _as_mapping(item)]
    if not groups:
        groups = _fallback_evidence_status_groups(evidence_radar_packet)
    counts = {group.get("key"): _evidence_group_count(group) for group in groups}
    if not any(counts.values()):
        return {}
    recovered = counts.get("recovered", 0)
    blocked = counts.get("blocked", 0)
    cached = counts.get("cached", 0)
    manual = counts.get("manual", 0)
    if blocked:
        status = "blocked"
        label = "证据分组受限"
        tone = "failed"
        guardrail = "仍受限证据未恢复前，乐观路径不能作为加仓依据。"
    elif cached or manual:
        status = "partial"
        label = "证据分组待复核"
        tone = "stale"
        guardrail = "缓存和待手动证据只能支撑观察，执行前需复核交易日和来源。"
    else:
        status = "ready"
        label = "证据分组已回流"
        tone = "ready"
        guardrail = "已回流证据可增强路径可信度，但仍需价格纪律确认。"
    items = []
    for group in groups:
        count = _evidence_group_count(group)
        if count <= 0:
            continue
        items.append(
            {
                "key": _to_text(group.get("key")),
                "label": _to_text(group.get("label"), "证据分组"),
                "count": count,
                "labels_text": _to_text(group.get("labels_text")) or _evidence_label_text(group.get("items"), fallback=f"{count} 项"),
                "tone": _to_text(group.get("tone"), "missing"),
                "deepseek_called": False,
            }
        )
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "summary": f"已回流 {recovered}｜仍受限 {blocked}｜缓存 {cached}｜待手动 {manual}",
        "guardrail": guardrail,
        "items": items,
        "deepseek_called": False,
    }


def _a_share_evidence_guidance(evidence_radar_packet: Any) -> dict:
    evidence = _as_mapping(evidence_radar_packet)
    if not evidence:
        return {}
    support = evidence.get("support_items")
    blockers = evidence.get("blocker_items")
    cached = evidence.get("cached_items")
    missing = evidence.get("missing_items")
    latest_impact = _as_mapping(
        evidence.get("latest_recovery_impact")
        or _as_mapping(evidence.get("radar_card")).get("latest_recovery_impact")
    )
    latest_state = _to_text(latest_impact.get("evidence_state"))
    latest_label = _to_text(latest_impact.get("label"), "最近恢复")
    latest_text = _to_text(latest_impact.get("impact_text"))
    legacy_path_notes = _legacy_a_share_path_evidence_notes(evidence)
    return {
        "summary": _to_text(evidence.get("decision_summary"), "支持 0｜阻断 0｜缓存 0｜缺失 0"),
        "support_text": _evidence_label_text(support),
        "blocker_text": _evidence_label_text(blockers),
        "cached_text": _evidence_label_text(cached),
        "missing_text": _evidence_label_text(missing),
        "has_support": bool(_as_list(support)),
        "has_blockers": bool(_as_list(blockers)),
        "has_cached": bool(_as_list(cached)),
        "has_missing": bool(_as_list(missing)),
        "latest_impact": latest_impact,
        "latest_state": latest_state,
        "latest_label": latest_label,
        "latest_text": latest_text,
        "has_latest_recovered": latest_state == "supporting",
        "has_latest_blocked": latest_state == "blocked",
        "has_latest_waiting": latest_state == "missing",
        "group_summary": _evidence_status_group_summary(evidence),
        "legacy_path_notes": legacy_path_notes,
    }


def _latest_recovery_projection_note(evidence: Mapping[str, Any], index: int) -> tuple[str, str, str]:
    latest_text = _to_text(evidence.get("latest_text"))
    latest_label = _to_text(evidence.get("latest_label"), "最近恢复")
    if not latest_text:
        return "", "", ""
    if evidence.get("has_latest_recovered"):
        if index == 0:
            return (
                f"最近恢复支持乐观路径：{latest_text}",
                "刚回流证据只提升可验证性，不等于自动加仓；仍需价格纪律确认。",
                "最近恢复已回流",
            )
        if index == 1:
            return (
                f"中性路径复核最近恢复：{latest_text}",
                "单项恢复不能替代完整证据链；保持触发条件优先。",
                "最近恢复待复核",
            )
        return (
            f"若{latest_label}回流后无法持续验证，谨慎路径仍优先。",
            "刚回流证据若过期或口径不一致，仍按保守路径处理。",
            "最近恢复防守线",
        )
    if evidence.get("has_latest_blocked"):
        if index == 0:
            return (
                f"最近恢复受限压制乐观路径：{latest_text}",
                "恢复受限前，乐观路径不能作为加仓依据。",
                "最近恢复仍受限",
            )
        if index == 1:
            return (
                f"中性路径等待最近恢复解除受限：{latest_text}",
                "恢复受限时维持观察，不扩大仓位。",
                "最近恢复待解除",
            )
        return (
            f"最近恢复仍受限触发谨慎边界：{latest_text}",
            "受限证据未解除前，优先保现金、降杠杆、收缩试探仓位。",
            "最近恢复阻断",
        )
    if evidence.get("has_latest_waiting"):
        if index == 0:
            return (
                f"最近恢复待验证，乐观路径只能等待：{latest_text}",
                "未检测到回流前，不能把缺失数据当成趋势确认。",
                "最近恢复待验证",
            )
        if index == 1:
            return (
                f"中性路径继续跟踪最近恢复：{latest_text}",
                "恢复待验证时不扩大仓位。",
                "最近恢复观察",
            )
        return (
            f"若最近恢复持续待验证，谨慎路径优先：{latest_text}",
            "证据未回流时按数据缺口处理。",
            "最近恢复缺口",
        )
    return "", "", ""


def _merge_a_share_evidence_guidance(paths: list[dict], evidence_radar_packet: Any, market_type: str) -> tuple[list[dict], str, dict, dict]:
    if market_type != "A股":
        return paths, "", {}, {}
    evidence = _a_share_evidence_guidance(evidence_radar_packet)
    if not evidence:
        return paths, "", {}, {}

    support_text = evidence["support_text"]
    blocker_text = evidence["blocker_text"]
    cached_text = evidence["cached_text"]
    missing_text = evidence["missing_text"]
    verification_text = []
    if evidence["has_cached"]:
        verification_text.append(f"缓存证据：{cached_text}")
    if evidence["has_missing"]:
        verification_text.append(f"缺失证据：{missing_text}")
    verification_summary = "；".join(verification_text) or "关键证据已刷新"
    legacy_notes = _as_mapping(evidence.get("legacy_path_notes"))
    legacy_support_text = _to_text(legacy_notes.get("support_text"))
    legacy_pending_text = _to_text(legacy_notes.get("pending_text"))
    legacy_risk_text = _to_text(legacy_notes.get("risk_text"))

    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        if index == 0:
            if evidence["has_support"]:
                note = f"支持证据增强乐观路径：{support_text}。"
            else:
                note = f"乐观路径待验证：先补齐{verification_summary}。"
            risk = (
                f"仍存在阻断证据：{blocker_text}，未排除前不能把乐观路径当作加仓依据。"
                if evidence["has_blockers"]
                else f"{verification_summary}；执行前仍需复核。"
            )
            if legacy_support_text:
                note = _append_evidence_text(note, f"旧能力已验证：{legacy_support_text}")
            if legacy_pending_text:
                risk = _append_evidence_text(risk, f"旧能力待验证限制乐观路径：{legacy_pending_text}")
            item["evidence_label"] = "支持证据增强" if evidence["has_support"] else "待验证"
        elif index == 1:
            note = f"中性路径重点复核：{verification_summary}。"
            risk = "缓存或缺失证据未补齐前，维持观察，不扩大仓位。"
            if legacy_support_text or legacy_pending_text:
                note = _append_evidence_text(note, f"中性路径复核旧能力：{legacy_support_text or legacy_pending_text}")
            if legacy_pending_text:
                risk = _append_evidence_text(risk, f"旧能力未完全回流：{legacy_pending_text}")
            item["evidence_label"] = "缓存/缺失待复核" if verification_text else "证据中性"
        else:
            if evidence["has_blockers"]:
                note = f"阻断证据触发谨慎路径：{blocker_text}。"
            else:
                note = f"若{verification_summary}迟迟无法确认，按谨慎边界管理。"
            risk = "阻断证据或数据缺口未排除前，优先保现金、降杠杆、收缩试探仓位。"
            if legacy_pending_text:
                note = _append_evidence_text(note, f"旧能力缺口触发谨慎边界：{legacy_pending_text}")
            elif legacy_support_text:
                note = _append_evidence_text(note, f"旧能力回流后的防守复核：{legacy_support_text}")
            if legacy_risk_text:
                risk = _append_evidence_text(risk, legacy_risk_text)
            item["evidence_label"] = "阻断证据优先" if evidence["has_blockers"] else "数据缺口防守"
        latest_note, latest_risk, latest_label = _latest_recovery_projection_note(evidence, index)
        if latest_note:
            note = _append_evidence_text(note, latest_note)
        if latest_risk:
            risk = _append_evidence_text(risk, latest_risk)
        if latest_label:
            item["latest_recovery_label"] = latest_label
        item["trigger"] = _append_evidence_text(item.get("trigger"), note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        item["evidence_note"] = note
        guided_paths.append(item)
    group_summary = _as_mapping(evidence.get("group_summary"))
    basis = f"A股证据雷达：{evidence['summary']}"
    if group_summary:
        basis = f"{basis}｜证据分组：{group_summary['summary']}"
    if evidence["latest_text"]:
        basis = f"{basis}｜最近恢复：{evidence['latest_label']} {evidence['latest_state'] or 'waiting'}"
    legacy_basis = "；".join(item for item in [legacy_support_text, legacy_pending_text] if item)
    if legacy_basis:
        basis = f"{basis}｜旧能力证据：{legacy_basis}"
    return guided_paths, basis, evidence["latest_impact"], group_summary


def _status_console_from_snapshot(home_snapshot: Any) -> dict:
    snapshot = _as_mapping(home_snapshot)
    diagnostic = _as_mapping(snapshot.get("a_share_user_data_diagnostic"))
    return _as_mapping(diagnostic.get("status_console"))


def _fact_recovery_from_snapshot(home_snapshot: Any) -> dict:
    snapshot = _as_mapping(home_snapshot)
    return _as_mapping(snapshot.get("a_share_fact_recovery_summary"))


def _a_share_data_capability_guidance(a_share_data_console: Any) -> dict:
    console = _as_mapping(a_share_data_console)
    if not console:
        return {}

    readiness = _to_text(console.get("decision_readiness_label")) or _to_text(console.get("headline")) or "待检测"
    summary = _to_text(console.get("summary"))
    groups = {
        _to_text(group.get("key")): _as_mapping(group)
        for group in _as_list(console.get("groups"))
        if _as_mapping(group)
    }

    def group_text(key: str, fallback: str) -> str:
        group = groups.get(key) or {}
        if _safe_int(group.get("count")) <= 0:
            return ""
        return _limited_join(group.get("items"), fallback=_to_text(group.get("summary")) or fallback)

    restricted_text = group_text("permission_denied", "受限数据")
    stale_text = group_text("stale_or_empty", "暂无数据")
    manual_text = group_text("manual_required", "待手动刷新")
    available_text = group_text("available", "可用数据")
    return {
        "readiness": readiness,
        "summary": summary,
        "restricted_text": restricted_text,
        "stale_text": stale_text,
        "manual_text": manual_text,
        "available_text": available_text,
        "has_restricted": bool(restricted_text),
        "has_stale": bool(stale_text),
        "has_manual": bool(manual_text),
        "has_available": bool(available_text),
    }


def _merge_a_share_data_capability_guidance(
    paths: list[dict],
    a_share_data_console: Any,
    market_type: str,
) -> tuple[list[dict], str]:
    if market_type != "A股":
        return paths, ""
    capability = _a_share_data_capability_guidance(a_share_data_console)
    if not capability:
        return paths, ""

    readiness = capability["readiness"]
    summary = capability["summary"]
    restricted_text = capability["restricted_text"]
    stale_text = capability["stale_text"]
    manual_text = capability["manual_text"]
    available_text = capability["available_text"]
    verification_parts = []
    if restricted_text:
        verification_parts.append(f"受限：{restricted_text}")
    if stale_text:
        verification_parts.append(f"暂无数据：{stale_text}")
    if manual_text:
        verification_parts.append(f"待手动：{manual_text}")
    if available_text:
        verification_parts.append(f"可用：{available_text}")
    verification_summary = "；".join(verification_parts) or summary or readiness

    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        if index == 0:
            if restricted_text:
                note = f"A股数据能力阻断乐观路径：受限数据 {restricted_text}。"
                risk = "受限数据未恢复前，不能把乐观路径当作加仓依据。"
            elif stale_text or manual_text:
                note = f"乐观路径需先补齐 A股数据能力：{verification_summary}。"
                risk = "数据未刷新或待手动时，只能把乐观路径视为待验证假设。"
            else:
                note = f"A股数据能力可进入证据链：{available_text or readiness}。"
                risk = "即使数据可用，仍需价格、纪律和仓位预算共振。"
            item["data_capability_label"] = readiness
        elif index == 1:
            note = f"中性路径复核 A股数据能力：{verification_summary}。"
            risk = "数据能力未完全恢复前，维持观察，不扩大仓位。"
            item["data_capability_label"] = "数据能力待复核"
        else:
            if restricted_text:
                note = f"受限数据触发谨慎路径：{restricted_text}。"
            elif stale_text or manual_text:
                note = f"数据缺口触发谨慎边界：{verification_summary}。"
            else:
                note = f"若可用数据转弱，谨慎路径优先：{available_text or readiness}。"
            risk = "A股数据能力受限、暂无或待手动时，优先保现金、降杠杆、收缩试探仓位。"
            item["data_capability_label"] = "数据能力防守线"
        item["trigger"] = _append_evidence_text(item.get("trigger"), note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        item["data_capability_note"] = note
        guided_paths.append(item)

    basis = f"A股数据能力：{readiness}"
    if summary:
        basis = f"{basis}｜{summary}"
    return guided_paths, basis


def _merge_data_health_ledger_guidance(
    paths: list[dict],
    data_health_ledger: Any,
    market_type: Any = None,
) -> tuple[list[dict], str, dict]:
    impact = build_data_health_impact_summary(data_health_ledger, market_type=market_type)
    if impact.get("status") == "missing":
        return paths, "", impact
    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        if index == 0:
            trigger_note = impact["projection_note"]
            risk = impact["risk_note"]
        elif index == 1:
            trigger_note = f"中性路径复核接口健康：{impact['summary']}"
            risk = "接口健康未完全确认前，维持观察，不扩大仓位。"
        else:
            trigger_note = f"谨慎路径优先检查接口健康：{impact['summary']}"
            risk = impact["risk_note"]
        item["trigger"] = _append_evidence_text(item.get("trigger"), trigger_note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        item["data_health_label"] = impact["label"]
        item["data_health_note"] = trigger_note
        guided_paths.append(item)
    return guided_paths, f"接口健康：{impact['label']}｜{impact['summary']}", impact


def _a_share_fact_recovery_guidance(a_share_fact_recovery_summary: Any) -> dict:
    summary = _as_mapping(a_share_fact_recovery_summary)
    if not summary:
        return {}
    items = []
    for raw in _as_list(summary.get("items")):
        item = _as_mapping(raw)
        if not item:
            continue
        items.append(
            {
                "key": _to_text(item.get("key")),
                "label": _to_text(item.get("label"), "A股事实"),
                "recovery_state": _to_text(item.get("recovery_state"), "waiting"),
                "status_label": _to_text(item.get("status_label"), "待验证"),
                "tone": _to_text(item.get("tone"), "missing"),
                "root_cause_label": _to_text(item.get("root_cause_label")),
                "source": _to_text(item.get("source"), "本地 packet"),
                "updated_at": _to_text(item.get("updated_at"), "暂无"),
                "deepseek_called": False,
            }
        )
    recovered = [item["label"] for item in items if item["recovery_state"] == "recovered"]
    blocked = [item["label"] for item in items if item["recovery_state"] == "blocked"]
    waiting = [item["label"] for item in items if item["recovery_state"] == "waiting"]
    text = _to_text(summary.get("summary"))
    if not text:
        total = _safe_int(summary.get("total_count")) or len(items) or 5
        text = (
            f"A股事实 {total} 项：已回流 {_safe_int(summary.get('recovered_count'))}"
            f"｜仍受限 {_safe_int(summary.get('blocked_count'))}"
            f"｜待验证 {_safe_int(summary.get('waiting_count'))}"
        )
    return {
        "summary": text,
        "tone": _to_text(summary.get("tone"), "missing"),
        "items": items,
        "detail_items": _a_share_fact_recovery_detail_items(items),
        "recovered_text": _limited_join(recovered, "暂无已回流事实"),
        "blocked_text": _limited_join(blocked, "暂无受限事实"),
        "waiting_text": _limited_join(waiting, "暂无待验证事实"),
        "has_recovered": bool(recovered),
        "has_blocked": bool(blocked),
        "has_waiting": bool(waiting),
        "next_action": _to_text(summary.get("next_action")),
    }


def _fact_recovery_detail_tone(state: str) -> str:
    if state == "recovered":
        return "success"
    if state == "blocked":
        return "danger"
    if state == "waiting":
        return "warning"
    return "muted"


def _fact_recovery_detail_label(state: str) -> str:
    return {
        "blocked": "受限事实",
        "waiting": "待验证事实",
        "recovered": "已回流事实",
    }.get(state, "A股事实")


def _fact_recovery_detail_guardrail(state: str, labels: str) -> str:
    target = labels or "A股事实"
    if state == "blocked":
        return f"{target} 仍受限，乐观路径不能写成加仓依据。"
    if state == "waiting":
        return f"{target} 待验证，路径只能保留低置信度或观察口径。"
    if state == "recovered":
        return f"{target} 可进入路径依据，但仍需价格、纪律和仓位共同确认。"
    return f"{target} 仅作为路径提示，不能替代交易纪律。"


def _fact_recovery_detail_path_impact(state: str, labels: str) -> str:
    target = labels or "A股事实"
    if state == "blocked":
        return f"压制乐观路径：先恢复 {target}，再判断是否允许试探仓位。"
    if state == "waiting":
        return f"降低路径置信度：{target} 未回流前，触发条件必须更严格。"
    if state == "recovered":
        return f"补强路径依据：{target} 已回流，可用于验证趋势/资金/风险。"
    return f"{target} 状态不明，路径维持待验证。"


def _a_share_fact_recovery_detail_items(items: list[dict]) -> list[dict]:
    detail_items = []
    for state in ("blocked", "waiting", "recovered"):
        rows = [
            item
            for item in items
            if _to_text(item.get("recovery_state")).lower() == state
        ]
        if not rows:
            continue
        labels = "、".join(_to_text(item.get("label")) for item in rows[:3] if _to_text(item.get("label")))
        root_causes = "、".join(
            _to_text(item.get("root_cause_label"))
            for item in rows[:3]
            if _to_text(item.get("root_cause_label"))
        )
        value = labels or _fact_recovery_detail_label(state)
        if root_causes and state != "recovered":
            value = f"{value}｜{root_causes}"
        detail_items.append(
            {
                "key": f"path_a_share_fact_{state}",
                "label": _fact_recovery_detail_label(state),
                "value": value,
                "tone": _fact_recovery_detail_tone(state),
                "count": len(rows),
                "guardrail": _fact_recovery_detail_guardrail(state, labels),
                "path_impact": _fact_recovery_detail_path_impact(state, labels),
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    return detail_items[:3]


def _merge_a_share_fact_recovery_guidance(
    paths: list[dict],
    a_share_fact_recovery_summary: Any,
    market_type: str,
) -> tuple[list[dict], str, list[dict], str, list[dict]]:
    if market_type != "A股":
        return paths, "", [], "", []
    recovery = _a_share_fact_recovery_guidance(a_share_fact_recovery_summary)
    if not recovery:
        return paths, "", [], "", []

    recovered_text = recovery["recovered_text"]
    blocked_text = recovery["blocked_text"]
    waiting_text = recovery["waiting_text"]
    detail_items = recovery.get("detail_items") or []
    blocked_detail = next((item for item in detail_items if item.get("key") == "path_a_share_fact_blocked"), {})
    waiting_detail = next((item for item in detail_items if item.get("key") == "path_a_share_fact_waiting"), {})
    recovered_detail = next((item for item in detail_items if item.get("key") == "path_a_share_fact_recovered"), {})
    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        if index == 0:
            if recovery["has_blocked"]:
                note = f"乐观路径仍需受限事实恢复：{blocked_text}。"
                risk = blocked_detail.get("guardrail") or "A股事实仍受限前，不把乐观路径当作加仓依据。"
                item["fact_recovery_path_impact"] = blocked_detail.get("path_impact")
            elif recovery["has_waiting"]:
                note = f"乐观路径需补齐待验证事实：{waiting_text}。"
                risk = waiting_detail.get("guardrail") or "待验证事实未回流前，只能小额观察，不放大仓位。"
                item["fact_recovery_path_impact"] = waiting_detail.get("path_impact")
            else:
                note = f"乐观路径已有事实回流支撑：{recovered_text}。"
                risk = recovered_detail.get("guardrail") or "事实已回流也不等于无风险，仍需价格和纪律共振。"
                item["fact_recovery_path_impact"] = recovered_detail.get("path_impact")
            item["fact_recovery_label"] = "事实回流乐观约束"
        elif index == 1:
            note = f"中性路径复核 A股事实回流：{recovery['summary']}。"
            risk = (waiting_detail or blocked_detail or recovered_detail).get("path_impact") or "事实回流不完整时，以观察和等待触发条件为主。"
            item["fact_recovery_path_impact"] = risk
            item["fact_recovery_label"] = "事实回流复核"
        else:
            if recovery["has_blocked"]:
                note = f"受限事实触发谨慎路径：{blocked_text}。"
                item["fact_recovery_path_impact"] = blocked_detail.get("path_impact")
            elif recovery["has_waiting"]:
                note = f"待验证事实触发谨慎边界：{waiting_text}。"
                item["fact_recovery_path_impact"] = waiting_detail.get("path_impact")
            else:
                note = f"若已回流事实转弱，谨慎路径优先：{recovered_text}。"
                item["fact_recovery_path_impact"] = recovered_detail.get("path_impact")
            risk = "A股事实受限或待验证时，优先保现金、降杠杆、收缩试探仓位。"
            item["fact_recovery_label"] = "事实回流防守线"
        item["trigger"] = _append_evidence_text(item.get("trigger"), note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        item["fact_recovery_note"] = note
        item["fact_recovery_detail_items"] = detail_items
        guided_paths.append(item)

    return guided_paths, f"A股事实回流：{recovery['summary']}", recovery["items"], recovery["tone"], detail_items


def build_projection_confidence_summary(projection_packet: Any = None) -> dict:
    packet = _as_mapping(projection_packet)
    if not packet:
        return {
            "status": "missing",
            "label": "路径待生成",
            "tone": "muted",
            "confidence_label": "不可验证",
            "summary": "趋势推演尚未生成；不能作为今日动作依据。",
            "guardrail": "先生成或读取趋势推演 packet，再进入策略执行和今日总决策。",
            "blocker_items": [],
            "pending_items": [],
            "support_items": [],
            "deepseek_called": False,
        }

    blocker_items = []
    pending_items = []
    support_items = []
    projection_status = _to_text(packet.get("status"), "waiting")
    path_basis = _to_text(packet.get("path_basis"))
    if projection_status == "waiting":
        pending_items.append("趋势推演待刷新")
    elif path_basis:
        support_items.append("路径依据已生成")

    evidence_group_status = _to_text(packet.get("path_evidence_group_status"))
    evidence_group_summary = _to_text(packet.get("path_evidence_group_summary"))
    evidence_group_label = _to_text(packet.get("path_evidence_group_label"), "A股证据分组")
    if evidence_group_status == "blocked":
        blocker_items.append(f"{evidence_group_label}：{evidence_group_summary or '仍受限'}")
    elif evidence_group_status == "partial":
        pending_items.append(f"{evidence_group_label}：{evidence_group_summary or '待复核'}")
    elif evidence_group_status == "ready":
        support_items.append(f"{evidence_group_label}：{evidence_group_summary or '已回流'}")

    recovery = _as_mapping(packet.get("path_recovery_impact"))
    recovery_state = _to_text(recovery.get("evidence_state"))
    recovery_label = _to_text(recovery.get("label"), "最近恢复")
    if recovery_state == "blocked":
        blocker_items.append(f"{recovery_label}仍受限")
    elif recovery_state == "missing":
        pending_items.append(f"{recovery_label}待验证")
    elif recovery_state == "supporting":
        support_items.append(f"{recovery_label}刚回流")

    health = _as_mapping(packet.get("path_data_health_impact"))
    health_status = _to_text(health.get("status"))
    if health_status == "blocked":
        blocker_items.append(_to_text(health.get("summary"), "接口健康阻断"))
    elif health_status == "partial":
        pending_items.append(_to_text(health.get("summary"), "接口健康待复核"))
    elif health_status == "ready":
        support_items.append(_to_text(health.get("summary"), "接口健康可用"))

    fact_tone = _to_text(packet.get("path_fact_recovery_tone"))
    fact_summary = _to_text(packet.get("path_fact_recovery_summary"))
    fact_detail_items = [
        _as_mapping(item)
        for item in _as_list(packet.get("path_fact_recovery_detail_items"))
        if _as_mapping(item)
    ]
    for item in fact_detail_items:
        label = _to_text(item.get("label"), "A股事实")
        value = _to_text(item.get("value"))
        detail_text = f"{label}：{value}" if value else label
        tone = _to_text(item.get("tone"))
        if tone in {"danger", "failed"}:
            blocker_items.append(detail_text)
        elif tone in {"warning", "stale", "missing"}:
            pending_items.append(detail_text)
        elif tone in {"success", "ready"}:
            support_items.append(detail_text)
    if fact_tone == "failed":
        blocker_items.append(fact_summary or "A股事实回流仍受限")
    elif fact_tone in {"stale", "missing", "warning"}:
        pending_items.append(fact_summary or "A股事实回流待验证")
    elif fact_summary:
        support_items.append(fact_summary)

    legacy_chain_status = _to_text(packet.get("path_legacy_decision_chain_status"))
    legacy_chain_summary = _to_text(packet.get("path_legacy_decision_chain_summary"))
    legacy_chain_label = _to_text(packet.get("path_legacy_decision_chain_label"), "旧能力决策链")
    if legacy_chain_status == "blocked":
        blocker_items.append(f"{legacy_chain_label}：{legacy_chain_summary or '仍有阻断项'}")
    elif legacy_chain_status in {"cache_only", "partial"}:
        pending_items.append(f"{legacy_chain_label}：{legacy_chain_summary or '缓存/待验证'}")
    elif legacy_chain_status == "ready":
        support_items.append(f"{legacy_chain_label}：{legacy_chain_summary or '已验证'}")

    if blocker_items:
        status = "blocked"
        label = "路径受限"
        tone = "danger"
        confidence_label = "低置信度"
        guardrail = "路径存在阻断项；不能把乐观路径当作加仓依据。"
    elif pending_items:
        status = "partial"
        label = "路径待验证"
        tone = "warning"
        confidence_label = "中低置信度"
        guardrail = "路径仍有待验证项；保持观察、小额试探或等待触发条件。"
    elif support_items:
        status = "ready"
        label = "路径可验证"
        tone = "success"
        confidence_label = "可验证"
        guardrail = "路径依据已形成，但仍需价格纪律、仓位预算和失效条件共同确认。"
    else:
        status = "missing"
        label = "路径待生成"
        tone = "muted"
        confidence_label = "不可验证"
        guardrail = "趋势推演没有可读依据，不进入交易动作判断。"

    summary_parts = []
    if blocker_items:
        summary_parts.append(f"阻断：{_limited_join(blocker_items, limit=2)}")
    if pending_items:
        summary_parts.append(f"待验证：{_limited_join(pending_items, limit=2)}")
    if support_items:
        summary_parts.append(f"支持：{_limited_join(support_items, limit=2)}")
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "confidence_label": confidence_label,
        "summary": "｜".join(summary_parts) or "趋势推演暂无可读依据。",
        "guardrail": guardrail,
        "path_basis": path_basis,
        "legacy_decision_chain_summary": legacy_chain_summary,
        "legacy_decision_chain_status": legacy_chain_status,
        "evidence_group_summary": evidence_group_summary,
        "evidence_group_status": evidence_group_status,
        "evidence_group_guardrail": _to_text(packet.get("path_evidence_group_guardrail")),
        "recovery_impact_summary": _to_text(packet.get("path_recovery_impact_summary")),
        "blocker_items": blocker_items[:5],
        "pending_items": pending_items[:5],
        "support_items": support_items[:5],
        "deepseek_called": bool(packet.get("deepseek_called")) is True,
    }


def build_projection_packet(
    decision_packet: Any = None,
    strategy_packet: Any = None,
    live_packet: Any = None,
    home_snapshot: Any = None,
    analysis_method_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
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
    position_context = _position_projection_context(snapshot, live, base)
    market_bias = _to_text(decision.get("market_bias") or _as_mapping(snapshot.get("today_action")).get("market_bias"), "未刷新")
    historical, historical_lineage = _real_historical_points(snapshot, live)
    if not historical:
        historical_lineage = _synthetic_historical_lineage(_to_text(position_context.get("price_basis"), "normalized"))
        historical = _historical_points(
            base,
            market_bias,
            source=historical_lineage["source"],
            source_label=historical_lineage["label"],
        )
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
                "source": "rule_scenario_projection",
                "source_label": "规则情景推演",
                "is_future_projection": True,
            }
        )
    paths, market_type, path_basis = _merge_path_guidance(paths, analysis_method_packet)
    paths, evidence_basis, latest_recovery_impact, evidence_group_summary = _merge_a_share_evidence_guidance(paths, evidence_radar_packet, market_type)
    data_console = _as_mapping(a_share_data_console) or _status_console_from_snapshot(snapshot)
    paths, data_capability_basis = _merge_a_share_data_capability_guidance(paths, data_console, market_type)
    health_ledger = _as_mapping(data_health_ledger) or _as_mapping(snapshot.get("data_health_ledger")) or _as_mapping(_as_mapping(snapshot.get("data_capability_console")).get("data_health_ledger"))
    paths, data_health_basis, data_health_impact = _merge_data_health_ledger_guidance(paths, health_ledger, market_type=market_type)
    fact_recovery = _as_mapping(a_share_fact_recovery_summary) or _fact_recovery_from_snapshot(snapshot)
    paths, fact_recovery_basis, fact_recovery_items, fact_recovery_tone, fact_recovery_detail_items = _merge_a_share_fact_recovery_guidance(
        paths,
        fact_recovery,
        market_type,
    )
    legacy_decision_chain = _as_mapping(snapshot.get("legacy_decision_chain_summary"))
    paths, legacy_decision_chain_basis, legacy_decision_chain_guidance = _merge_legacy_decision_chain_guidance(
        paths,
        legacy_decision_chain,
    )
    paths = _merge_position_context_into_paths(paths, position_context, base)
    fallback = status == "waiting" or not _has_payload(decision, strategy, live, snapshot)
    note = "示例路径 / 待刷新" if fallback else "基于现有结构化 packet 的条件化路径推演"
    future_lineage = {
        "source": "rule_scenario_projection",
        "label": "规则情景推演",
        "data_source": "本地规则 + 结构化结果",
        "uses_real_future_price": False,
        "summary": "未来三路径由本地规则情景生成，叠加今日总决策、策略执行、市场分析方法、A股证据/数据能力和持仓风险预算。",
        "inputs": [
            "strategy_execution_packet",
            "command_center_decision_packet",
            "analysis_method_packet",
            "a_share_evidence_radar",
            "data_capability",
            "risk_budget",
            "current_price",
            "cost_price",
        ],
        "gaps": ["未来路径不是未来真实价格；必须按触发条件验证。"],
    }
    lineage_gaps = list(dict.fromkeys([*(historical_lineage.get("gaps") or []), *(future_lineage.get("gaps") or [])]))
    data_lineage = {
        "historical": historical_lineage,
        "future": future_lineage,
        "updated_at": updated_at,
        "summary": f"历史段：{historical_lineage.get('label')}；未来段：{future_lineage.get('label')}。",
        "gaps": lineage_gaps,
        "deepseek_called": False,
    }
    return {
        "status": status,
        "horizon_days": horizon,
        "base_date": _date_text(base_date or updated_at, now=now),
        "historical": historical,
        "paths": paths,
        "market_type": market_type,
        "path_basis": " ｜ ".join(
            [
                item
                for item in [
                    path_basis,
                    evidence_basis,
                    data_capability_basis,
                    data_health_basis,
                    fact_recovery_basis,
                    legacy_decision_chain_basis,
                ]
                if item
            ]
        ),
        "path_evidence_summary": evidence_basis,
        "path_evidence_group_summary": _to_text(evidence_group_summary.get("summary")),
        "path_evidence_group_status": _to_text(evidence_group_summary.get("status")),
        "path_evidence_group_label": _to_text(evidence_group_summary.get("label")),
        "path_evidence_group_guardrail": _to_text(evidence_group_summary.get("guardrail")),
        "path_evidence_group_items": evidence_group_summary.get("items") or [],
        "path_recovery_impact": latest_recovery_impact,
        "path_recovery_impact_summary": _to_text(latest_recovery_impact.get("impact_text")),
        "path_data_capability_summary": data_capability_basis,
        "path_data_health_summary": data_health_basis,
        "path_data_health_impact": data_health_impact,
        "path_fact_recovery_summary": fact_recovery_basis,
        "path_fact_recovery_items": fact_recovery_items,
        "path_fact_recovery_detail_items": fact_recovery_detail_items,
        "path_fact_recovery_tone": fact_recovery_tone,
        "path_legacy_decision_chain_summary": _to_text(legacy_decision_chain_guidance.get("summary")),
        "path_legacy_decision_chain_status": _to_text(legacy_decision_chain_guidance.get("status")),
        "path_legacy_decision_chain_label": _to_text(legacy_decision_chain_guidance.get("label")),
        "path_legacy_decision_chain_items": legacy_decision_chain_guidance.get("items") or [],
        "position_context": position_context,
        "reference_lines": position_context.get("reference_lines") or [],
        "position_context_summary": _to_text(position_context.get("summary")),
        "market_method_summary": _to_text(_as_mapping(analysis_method_packet).get("summary"), "分析方法待验证"),
        "historical_source": historical_lineage.get("source"),
        "historical_source_label": historical_lineage.get("label"),
        "historical_data_lineage": historical_lineage,
        "future_source": future_lineage.get("source"),
        "future_source_label": future_lineage.get("label"),
        "future_data_lineage": future_lineage,
        "data_lineage": data_lineage,
        "lineage_summary": data_lineage["summary"],
        "lineage_gaps": lineage_gaps,
        "source": SOURCE_FALLBACK if fallback else SOURCE_READY,
        "updated_at": updated_at,
        "deepseek_called": False,
        "is_fallback": fallback,
        "note": note,
        "base_value": round(base, 4),
        "unit": "price" if position_context.get("price_basis") == "real_price" else "index",
    }


def build_projection_packet_from_state(
    state: Any = None,
    live_packet: Any = None,
    home_snapshot: Any = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    now: Any = None,
) -> dict:
    state_map = _as_mapping(state)
    snapshot = _as_mapping(home_snapshot or state_map.get("command_center_home_snapshot"))
    return build_projection_packet(
        decision_packet=state_map.get("command_center_decision_packet") or state_map.get("command_center_decision_last_success"),
        strategy_packet=state_map.get("strategy_execution_packet") or state_map.get("strategy_execution_last_success"),
        live_packet=live_packet or state_map.get("command_center_live_packet"),
        home_snapshot=snapshot,
        analysis_method_packet=state_map.get("command_center_analysis_method_packet"),
        evidence_radar_packet=state_map.get("command_center_evidence_radar_packet"),
        a_share_data_console=state_map.get("command_center_a_share_data_console") or _status_console_from_snapshot(snapshot),
        data_health_ledger=state_map.get("command_center_data_health_ledger") or snapshot.get("data_health_ledger"),
        a_share_fact_recovery_summary=state_map.get("command_center_a_share_fact_recovery_summary") or _fact_recovery_from_snapshot(snapshot),
        horizon_days=horizon_days,
        now=now,
    )
