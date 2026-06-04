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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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


def _merge_a_share_evidence_guidance(paths: list[dict], evidence_radar_packet: Any, market_type: str) -> tuple[list[dict], str, dict]:
    if market_type != "A股":
        return paths, "", {}
    evidence = _a_share_evidence_guidance(evidence_radar_packet)
    if not evidence:
        return paths, "", {}

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
            item["evidence_label"] = "支持证据增强" if evidence["has_support"] else "待验证"
        elif index == 1:
            note = f"中性路径重点复核：{verification_summary}。"
            risk = "缓存或缺失证据未补齐前，维持观察，不扩大仓位。"
            item["evidence_label"] = "缓存/缺失待复核" if verification_text else "证据中性"
        else:
            if evidence["has_blockers"]:
                note = f"阻断证据触发谨慎路径：{blocker_text}。"
            else:
                note = f"若{verification_summary}迟迟无法确认，按谨慎边界管理。"
            risk = "阻断证据或数据缺口未排除前，优先保现金、降杠杆、收缩试探仓位。"
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
    basis = f"A股证据雷达：{evidence['summary']}"
    if evidence["latest_text"]:
        basis = f"{basis}｜最近恢复：{evidence['latest_label']} {evidence['latest_state'] or 'waiting'}"
    return guided_paths, basis, evidence["latest_impact"]


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
        "recovered_text": _limited_join(recovered, "暂无已回流事实"),
        "blocked_text": _limited_join(blocked, "暂无受限事实"),
        "waiting_text": _limited_join(waiting, "暂无待验证事实"),
        "has_recovered": bool(recovered),
        "has_blocked": bool(blocked),
        "has_waiting": bool(waiting),
        "next_action": _to_text(summary.get("next_action")),
    }


def _merge_a_share_fact_recovery_guidance(
    paths: list[dict],
    a_share_fact_recovery_summary: Any,
    market_type: str,
) -> tuple[list[dict], str, list[dict], str]:
    if market_type != "A股":
        return paths, "", [], ""
    recovery = _a_share_fact_recovery_guidance(a_share_fact_recovery_summary)
    if not recovery:
        return paths, "", [], ""

    recovered_text = recovery["recovered_text"]
    blocked_text = recovery["blocked_text"]
    waiting_text = recovery["waiting_text"]
    guided_paths = []
    for index, path in enumerate(paths):
        item = dict(path)
        if index == 0:
            if recovery["has_blocked"]:
                note = f"乐观路径仍需受限事实恢复：{blocked_text}。"
                risk = "A股事实仍受限前，不把乐观路径当作加仓依据。"
            elif recovery["has_waiting"]:
                note = f"乐观路径需补齐待验证事实：{waiting_text}。"
                risk = "待验证事实未回流前，只能小额观察，不放大仓位。"
            else:
                note = f"乐观路径已有事实回流支撑：{recovered_text}。"
                risk = "事实已回流也不等于无风险，仍需价格和纪律共振。"
            item["fact_recovery_label"] = "事实回流乐观约束"
        elif index == 1:
            note = f"中性路径复核 A股事实回流：{recovery['summary']}。"
            risk = "事实回流不完整时，以观察和等待触发条件为主。"
            item["fact_recovery_label"] = "事实回流复核"
        else:
            if recovery["has_blocked"]:
                note = f"受限事实触发谨慎路径：{blocked_text}。"
            elif recovery["has_waiting"]:
                note = f"待验证事实触发谨慎边界：{waiting_text}。"
            else:
                note = f"若已回流事实转弱，谨慎路径优先：{recovered_text}。"
            risk = "A股事实受限或待验证时，优先保现金、降杠杆、收缩试探仓位。"
            item["fact_recovery_label"] = "事实回流防守线"
        item["trigger"] = _append_evidence_text(item.get("trigger"), note)
        item["risk"] = _append_evidence_text(item.get("risk"), risk)
        item["risk_note"] = item["risk"]
        item["fact_recovery_note"] = note
        guided_paths.append(item)

    return guided_paths, f"A股事实回流：{recovery['summary']}", recovery["items"], recovery["tone"]


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
    if fact_tone == "failed":
        blocker_items.append(fact_summary or "A股事实回流仍受限")
    elif fact_tone in {"stale", "missing", "warning"}:
        pending_items.append(fact_summary or "A股事实回流待验证")
    elif fact_summary:
        support_items.append(fact_summary)

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
    paths, evidence_basis, latest_recovery_impact = _merge_a_share_evidence_guidance(paths, evidence_radar_packet, market_type)
    data_console = _as_mapping(a_share_data_console) or _status_console_from_snapshot(snapshot)
    paths, data_capability_basis = _merge_a_share_data_capability_guidance(paths, data_console, market_type)
    health_ledger = _as_mapping(data_health_ledger) or _as_mapping(snapshot.get("data_health_ledger")) or _as_mapping(_as_mapping(snapshot.get("data_capability_console")).get("data_health_ledger"))
    paths, data_health_basis, data_health_impact = _merge_data_health_ledger_guidance(paths, health_ledger, market_type=market_type)
    fact_recovery = _as_mapping(a_share_fact_recovery_summary) or _fact_recovery_from_snapshot(snapshot)
    paths, fact_recovery_basis, fact_recovery_items, fact_recovery_tone = _merge_a_share_fact_recovery_guidance(
        paths,
        fact_recovery,
        market_type,
    )
    fallback = status == "waiting" or not _has_payload(decision, strategy, live, snapshot)
    note = "示例路径 / 待刷新" if fallback else "基于现有结构化 packet 的条件化路径推演"
    return {
        "status": status,
        "horizon_days": horizon,
        "base_date": _date_text(base_date or updated_at, now=now),
        "historical": _historical_points(base, market_bias),
        "paths": paths,
        "market_type": market_type,
        "path_basis": " ｜ ".join([item for item in [path_basis, evidence_basis, data_capability_basis, data_health_basis, fact_recovery_basis] if item]),
        "path_evidence_summary": evidence_basis,
        "path_recovery_impact": latest_recovery_impact,
        "path_recovery_impact_summary": _to_text(latest_recovery_impact.get("impact_text")),
        "path_data_capability_summary": data_capability_basis,
        "path_data_health_summary": data_health_basis,
        "path_data_health_impact": data_health_impact,
        "path_fact_recovery_summary": fact_recovery_basis,
        "path_fact_recovery_items": fact_recovery_items,
        "path_fact_recovery_tone": fact_recovery_tone,
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
