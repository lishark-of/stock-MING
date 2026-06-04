from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_data_health_ledger import build_data_health_impact_summary
from command_center_projection import build_projection_confidence_summary


DATA_STATUS_LABELS = {
    "quant": "量化",
    "backtest": "纪律/回测",
    "live_packet": "综合包",
}

DATA_STATUS_STATE_LABELS = {
    "ready": "已就绪",
    "cached": "使用缓存",
    "missing": "待刷新",
    "failed": "失败",
    "waiting": "待刷新",
}

DEFAULT_PATHS = (
    {"name": "乐观路径", "condition": "数据补齐且市场、量化、纪律转为同向。", "action": "只允许小幅试探。", "risk": "仍不追高、不一次性重仓。"},
    {"name": "中性路径", "condition": "信号继续分歧或缺少新增验证。", "action": "等待或只观察。", "risk": "避免在无验证条件下频繁交易。"},
    {"name": "谨慎路径", "condition": "纪律信号转弱、回撤扩大或数据失败。", "action": "降风险。", "risk": "优先保现金、降杠杆、减少暴露。"},
)


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip()


def _money_text(value: Any) -> str:
    if value in [None, ""]:
        return "暂无"
    try:
        if isinstance(value, str):
            number = float(value.replace(",", "").replace("¥", "").strip())
        else:
            number = float(value)
        return f"¥{number:,.0f}"
    except Exception:
        return _to_text(value) or "暂无"


def normalize_strategy_status(packet: Any) -> str:
    payload = _as_mapping(packet)
    raw = _to_text(payload.get("status")).lower()
    if raw in {"waiting", "ready", "failed"}:
        return raw
    if raw in {"ok", "completed", "complete", "success"}:
        return "ready"
    return "waiting" if not payload else "ready"


def strategy_status_label(packet: Any) -> str:
    return {
        "waiting": "待生成",
        "ready": "策略建议已生成",
        "failed": "失败后缓存",
    }.get(normalize_strategy_status(packet), "待生成")


def strategy_status_tone(packet: Any) -> str:
    return {
        "waiting": "muted",
        "ready": "success",
        "failed": "danger",
    }.get(normalize_strategy_status(packet), "muted")


def strategy_action_label(packet: Any) -> str:
    payload = _as_mapping(packet)
    action = _to_text(payload.get("action") or payload.get("overall_action"))
    mapping = {
        "买入": "买入（需验证）",
        "卖出": "卖出 / 降风险",
        "小幅试探": "可轻仓试探",
        "小幅进攻": "可轻仓试探",
        "持仓观察": "可持有",
        "允许进攻": "可加仓",
    }
    return mapping.get(action, action or "等待")


def strategy_action_tone(packet: Any) -> str:
    action = strategy_action_label(packet)
    if any(key in action for key in ["卖出", "降风险", "减仓", "退出", "止损", "风险"]):
        return "danger"
    if any(key in action for key in ["等待", "观察", "尚未生成"]):
        return "warning"
    return "success"


def strategy_confidence_tone(packet: Any) -> str:
    confidence = _to_text(_as_mapping(packet).get("confidence")) or "低"
    if confidence == "高":
        return "success"
    if confidence == "中":
        return "warning"
    return "muted"


def strategy_action_guardrail_text(packet: Any) -> str:
    action = strategy_action_label(packet)
    if any(key in action for key in ["买入", "小幅进攻", "试探", "可轻仓", "可加仓"]):
        return "只允许小额试探，必须等验证条件，不追高、不冲动加杠杆。"
    if any(key in action for key in ["卖出", "降风险", "减仓", "退出", "止损"]):
        return "优先减暴露、降杠杆、保现金，暂停新增风险。"
    if any(key in action for key in ["等待", "观察", "尚未生成"]):
        return "今天不是必须交易，等待数据和纪律条件补齐。"
    return "策略建议只给路径，执行前仍需复核纪律和资金预算。"


def strategy_user_boundary_text(packet: Any) -> str:
    del packet
    return "策略执行卡只读取缓存、量化摘要和纪律结果；不自动调用 DeepSeek、不自动回测、不构成收益承诺。"


def build_strategy_path_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    paths = payload.get("next_5_10_day_paths") or payload.get("paths") or payload.get("scenario_paths") or []
    if not isinstance(paths, list):
        paths = []
    source = paths[:3] if paths else list(DEFAULT_PATHS)
    names = ["乐观路径", "中性路径", "防守路径"]
    items = []
    for index, item in enumerate(source[:3]):
        path = _as_mapping(item)
        if path:
            items.append(
                {
                    "name": _to_text(path.get("name")) or names[index],
                    "condition": _to_text(path.get("condition") or path.get("trigger")) or "等待验证条件。",
                    "action": _to_text(path.get("action") or path.get("advice")) or "只观察。",
                    "risk": _to_text(path.get("risk") or path.get("risk_note")) or _path_risk_text(path, index),
                    "tone": _path_tone(path, index),
                }
            )
        else:
            items.append({"name": names[index], "condition": _to_text(item) or "等待验证。", "action": "按纪律执行。", "risk": _path_risk_text({}, index), "tone": _path_tone({}, index)})
    return items


def _path_risk_text(path: Mapping[str, Any], index: int) -> str:
    text = _to_text(path.get("name")) + " " + _to_text(path.get("action"))
    if any(key in text for key in ["谨慎", "防守", "降风险", "减仓", "退出"]):
        return "若触发该路径，先控制亏损和杠杆，不新增风险。"
    if any(key in text for key in ["乐观", "进攻", "试探", "买入", "加仓"]):
        return "只允许小额执行，禁止追高、满仓和临时加杠杆。"
    if index == 0:
        return "即使转强，也需要验证条件落地后再动。"
    if index == 2:
        return "一旦纪律转弱，优先减暴露和保现金。"
    return "没有新验证前，避免把观察误解为买入。"


def _path_tone(path: Mapping[str, Any], index: int) -> str:
    text = _to_text(path.get("name")) + " " + _to_text(path.get("action"))
    if any(key in text for key in ["谨慎", "防守", "降风险", "减仓", "退出"]):
        return "danger"
    if any(key in text for key in ["乐观", "进攻", "试探", "买入", "加仓"]):
        return "success"
    return "warning" if index == 1 else "muted"


def build_strategy_condition_items(packet: Any) -> dict:
    payload = _as_mapping(packet)
    return {
        "add": _to_text(payload.get("add_condition")) or "等待量化、纪律和市场至少两项同向后再考虑。",
        "reduce": _to_text(payload.get("reduce_condition")) or "触发止损、减仓或风险预算失效时优先降低暴露。",
        "invalidation": _to_text(payload.get("invalidation_condition")) or "市场环境转弱或纪律信号反向时，本轮建议失效。",
    }


def build_strategy_condition_cards(packet: Any) -> list[dict]:
    conditions = build_strategy_condition_items(packet)
    return [
        {"key": "add", "label": "加仓条件", "value": conditions["add"], "tone": "success", "check_label": "满足后才允许小额试探"},
        {"key": "reduce", "label": "减仓条件", "value": conditions["reduce"], "tone": "warning", "check_label": "触发后优先降低暴露"},
        {"key": "invalidation", "label": "失效条件", "value": conditions["invalidation"], "tone": "danger", "check_label": "触发后本轮建议作废"},
    ]


def build_strategy_discipline_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    discipline = _as_mapping(payload.get("discipline_check"))
    warnings = discipline.get("warnings") or payload.get("warnings") or []
    action = strategy_action_label(payload)
    data_status = _as_mapping(payload.get("data_status"))
    lines = [
        ("是否违反交易纪律", "待刷新" if discipline.get("status") in [None, "", "missing"] else ("需复核" if warnings else "未发现明确违反")),
        ("是否需要等待确认", "是" if action in {"等待", "只观察", "尚未生成"} else "按条件执行"),
        ("纪律状态", _data_status_label(discipline.get("status"))),
        ("最新信号", _to_text(discipline.get("latest_signal")) or "待刷新"),
        ("胜率", _to_text(discipline.get("win_rate")) or "待刷新"),
        ("最大回撤", _to_text(discipline.get("max_drawdown")) or "待刷新"),
        ("是否禁止追高", "是"),
        ("是否禁止自动重仓", "是"),
    ]
    if (_to_text(payload.get("confidence")) or "低") == "低" or "missing" in set(_to_text(value) for value in data_status.values()):
        lines.append(("数据覆盖", "不足 / 建议谨慎"))
    return [{"label": label, "value": value, "tone": _discipline_tone(label, value)} for label, value in lines]


def _discipline_tone(label: str, value: str) -> str:
    text = f"{label} {value}"
    if any(key in text for key in ["需复核", "不足", "风险", "回撤", "失败"]):
        return "danger"
    if any(key in text for key in ["待刷新", "待确认", "等待"]):
        return "warning"
    return "success"


def build_strategy_risk_budget_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    budget = _as_mapping(payload.get("risk_budget"))
    position_mode = _to_text(budget.get("position_mode") or payload.get("position_mode")) or "待确认"
    position_advice = _to_text(payload.get("position_advice")) or f"{position_mode}：等待策略执行建议补齐。"
    items = [
        {"label": "仓位建议", "value": position_advice, "tone": "warning" if "等待" in position_advice or "观察" in position_advice else "success"},
        {"label": "当前建议仓位", "value": position_mode, "tone": "muted" if position_mode in {"未知", "待确认"} else "success"},
        {"label": "可加仓金额", "value": _money_text(budget.get("max_add_amount")), "tone": "muted" if budget.get("max_add_amount") in [None, ""] else "success"},
        {"label": "现金缓冲", "value": _money_text(budget.get("cash_buffer")), "tone": "warning" if budget.get("cash_buffer") in [None, ""] else "success"},
    ]
    financing = _to_text(budget.get("margin_mode") or budget.get("financing_advice") or payload.get("margin_mode") or payload.get("financing_advice"))
    if financing:
        items.append({"label": "融资建议", "value": financing, "tone": "danger" if "禁止" in financing or "降低" in financing else "warning"})
    return items[:5]


def build_strategy_data_status_items(packet: Any) -> list[dict]:
    data_status = _as_mapping(_as_mapping(packet).get("data_status"))
    return [
        {"key": key, "label": label, "state": _to_text(data_status.get(key)) or "missing", "text": _data_status_label(data_status.get(key))}
        for key, label in DATA_STATUS_LABELS.items()
    ]


def build_market_method_guidance(analysis_method_packet: Any = None) -> dict:
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market")) or "市场类型待确认"
    if market == "A股":
        focus = ["资金流", "MA20/MA60", "公告风险", "龙虎榜/融资融券"]
        return {
            "market": market,
            "title": "A股验证重点",
            "focus_items": focus,
            "add_condition": "站稳 MA20、量能确认、资金流改善，且公告无新增负面。",
            "reduce_condition": "跌破 MA20/MA60、资金流恶化，或出现监管 / 减持风险。",
            "invalidation_condition": "题材退潮、龙虎榜 / 融资数据不支持，或放量下跌。",
        }
    if market == "美股":
        focus = ["RS 相对强弱", "财报/指引", "行业轮动", "宏观利率"]
        return {
            "market": market,
            "title": "美股验证重点",
            "focus_items": focus,
            "add_condition": "RS 走强、财报后确认、行业强于指数，并突破关键价位。",
            "reduce_condition": "财报 / 指引转弱、跌破趋势线，或宏观利率持续压制。",
            "invalidation_condition": "增长逻辑失效，指数和行业共振走弱。",
        }
    if market == "ETF":
        focus = ["赛道强度", "回踩确认", "成交额/流动性", "持仓重叠"]
        return {
            "market": market,
            "title": "ETF 验证重点",
            "focus_items": focus,
            "add_condition": "赛道强度确认、回踩不破、成交额充足，且同赛道不重复配置。",
            "reduce_condition": "赛道过热、跌破均线、流动性变差，或溢价折价异常。",
            "invalidation_condition": "主题轮动失败，跟踪指数趋势破位。",
        }
    return {
        "market": market,
        "title": "市场验证重点",
        "focus_items": ["市场类型", "基础数据", "纪律结果"],
        "add_condition": "先确认市场类型和基础数据，再讨论加仓。",
        "reduce_condition": "数据缺口扩大或纪律转弱时先降风险。",
        "invalidation_condition": "市场画像无法确认时，本轮策略只保留观察。",
    }


def _evidence_validation_tone(evidence_state: str) -> str:
    if evidence_state == "blocked":
        return "danger"
    if evidence_state in {"missing", "cached"}:
        return "warning"
    return "success"


def _evidence_validation_action(label: str, evidence_state: str) -> str:
    if evidence_state == "blocked":
        return f"先排除 {label} 阻断项；未排除前不应加仓或放大仓位。"
    if evidence_state == "missing":
        return f"先补齐 {label}；缺失时只能保留观察或谨慎路径。"
    if evidence_state == "cached":
        return f"复核 {label} 缓存日期和口径；过期缓存不能当作今日事实。"
    return f"{label}可作为辅助证据，但仍需价格、纪律和仓位共振。"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _limited_text_join(value: Any, fallback: str = "暂无明细", limit: int = 2) -> str:
    values = []
    if isinstance(value, (list, tuple, set)):
        values = [_to_text(item) for item in value]
    else:
        text = _to_text(value)
        values = [text] if text else []
    values = [item for item in values if item]
    if not values:
        return fallback
    suffix = f" 等 {len(values)} 项" if len(values) > limit else ""
    return "、".join(values[:limit]) + suffix


def _evidence_group_count(group: Mapping[str, Any]) -> int:
    try:
        return max(0, int(float(group.get("count"))))
    except Exception:
        return len([item for item in _as_list(group.get("items")) if _as_mapping(item)])


def _fallback_evidence_status_groups(evidence_radar_packet: Mapping[str, Any]) -> list[dict]:
    group_configs = [
        ("recovered", "已回流", "ready", evidence_radar_packet.get("support_items")),
        ("blocked", "仍受限", "failed", evidence_radar_packet.get("blocker_items")),
        ("cached", "使用缓存", "stale", evidence_radar_packet.get("cached_items")),
        ("manual", "待手动", "missing", evidence_radar_packet.get("missing_items")),
    ]
    groups = []
    for key, label, tone, raw_items in group_configs:
        items = [_as_mapping(item) for item in _as_list(raw_items) if _as_mapping(item)]
        labels = [_to_text(item.get("label")) for item in items]
        groups.append(
            {
                "key": key,
                "label": label,
                "tone": tone,
                "count": len(items),
                "labels_text": "、".join([item for item in labels if item][:4]) or "无",
                "items": items,
                "deepseek_called": False,
            }
        )
    return groups


def _evidence_group_highlights(groups: list[dict]) -> list[dict]:
    highlights = []
    for group in groups:
        count = _evidence_group_count(group)
        if count <= 0:
            continue
        labels_text = _to_text(group.get("labels_text")) or _limited_text_join(
            [_to_text(_as_mapping(item).get("label")) for item in _as_list(group.get("items")) if _as_mapping(item)],
            fallback=f"{count} 项",
            limit=3,
        )
        highlights.append(
            {
                "key": _to_text(group.get("key")) or "evidence_group",
                "label": _to_text(group.get("label")) or "证据分组",
                "count": count,
                "labels_text": labels_text,
                "tone": _to_text(group.get("tone")) or "missing",
                "deepseek_called": False,
            }
        )
    return highlights


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
    text = _to_text(
        item.get("headline")
        or item.get("metric")
        or item.get("status_label")
        or item.get("evidence_label")
        or item.get("label")
    )
    return text or fallback


def _legacy_a_share_strategy_condition_notes(evidence: Mapping[str, Any]) -> dict:
    configs = {
        "limit_emotion": {
            "label": "涨跌停/情绪",
            "supporting_add": "已回流，加仓仍必须避开追高和涨跌停情绪边界",
            "supporting_reduce": "若情绪转弱或冲板失败，减仓/降风险优先级上调",
            "supporting_invalidation": "题材热度退潮或涨跌停风险恶化时，乐观路径失效",
            "pending_add": "未验证前不支持追高、加融资或把情绪当作买入依据",
            "pending_reduce": "情绪边界未确认时，减仓条件优先于加仓条件",
            "pending_invalidation": "不能确认题材温度和涨跌停风险时，本轮进攻假设降级",
        },
        "chip_radar": {
            "label": "筹码/胜率",
            "supporting_add": "已回流，加仓前仍需复核压力位、获利盘和胜率口径",
            "supporting_reduce": "获利盘压力偏高或压力位失守时，先减暴露",
            "supporting_invalidation": "筹码压力和胜率口径转弱时，本轮策略建议失效",
            "pending_add": "未验证前不能把压力位或胜率写成加仓依据",
            "pending_reduce": "筹码压力缺失时，价格走弱优先触发减仓/降风险",
            "pending_invalidation": "筹码/胜率无法回流时，乐观执行条件不完整",
        },
    }
    add_notes = []
    reduce_notes = []
    invalidation_notes = []
    items = []
    for key, config in configs.items():
        state, item = _first_evidence_item(evidence, key)
        if not state:
            continue
        label = config["label"]
        brief = _evidence_item_brief(item, label)
        prefix = f"{label}：{brief}"
        is_supporting = state == "supporting"
        state_key = "supporting" if is_supporting else "pending"
        add_notes.append(f"{prefix}；{config[state_key + '_add']}")
        reduce_notes.append(f"{prefix}；{config[state_key + '_reduce']}")
        invalidation_notes.append(f"{prefix}；{config[state_key + '_invalidation']}")
        items.append(
            {
                "key": key,
                "label": label,
                "state": state,
                "state_label": _to_text(item.get("evidence_label") or item.get("status_label")) or "待验证",
                "summary": prefix,
                "deepseek_called": False,
            }
        )
    return {
        "add_note": "；".join(add_notes),
        "reduce_note": "；".join(reduce_notes),
        "invalidation_note": "；".join(invalidation_notes),
        "items": items,
        "deepseek_called": False,
    }


def build_strategy_a_share_evidence_group_guidance(evidence_radar_packet: Any = None) -> dict:
    evidence = _as_mapping(evidence_radar_packet)
    if not evidence:
        return {}
    groups = [_as_mapping(item) for item in _as_list(evidence.get("evidence_status_groups")) if _as_mapping(item)]
    if not groups:
        groups = _fallback_evidence_status_groups(evidence)
    counts = {group.get("key"): _evidence_group_count(group) for group in groups}
    if not any(counts.values()):
        return {}
    legacy_condition_notes = _legacy_a_share_strategy_condition_notes(evidence)

    recovered = counts.get("recovered", 0)
    blocked = counts.get("blocked", 0)
    cached = counts.get("cached", 0)
    manual = counts.get("manual", 0)
    summary = f"已回流 {recovered}｜仍受限 {blocked}｜缓存 {cached}｜待手动 {manual}"
    if blocked:
        status = "blocked"
        tone = "danger"
        add_guardrail = "仍受限证据未恢复前，不支持加仓、追高或加融资；只能观察、小额试探或降风险。"
        reduce_guardrail = "若价格走弱且阻断证据未排除，优先减暴露、降杠杆、保现金。"
        invalidation_guardrail = "公告硬风险、龙虎榜、融资等关键证据持续受限时，本轮进攻路径失效。"
    elif cached or manual:
        status = "partial"
        tone = "warning"
        add_guardrail = "缓存和待手动证据只能辅助观察；加仓前需复核交易日、来源和回流 packet。"
        reduce_guardrail = "缓存过期或待手动项无法验证时，减仓条件优先级上调。"
        invalidation_guardrail = "关键证据超过有效交易日或无法回流时，本轮乐观路径降级为待验证。"
    else:
        status = "ready"
        tone = "success"
        add_guardrail = "已回流证据可作为加仓条件的辅助依据，但仍需 MA/量能/纪律和仓位预算共振。"
        reduce_guardrail = "已回流证据若转弱或和价格纪律冲突，按纪律线减仓。"
        invalidation_guardrail = "证据链从支持转为分歧或失败时，本轮策略建议失效并重新生成。"
    if legacy_condition_notes.get("add_note"):
        add_guardrail = f"{add_guardrail} 旧能力验证：{legacy_condition_notes['add_note']}。"
    if legacy_condition_notes.get("reduce_note"):
        reduce_guardrail = f"{reduce_guardrail} 旧能力验证：{legacy_condition_notes['reduce_note']}。"
    if legacy_condition_notes.get("invalidation_note"):
        invalidation_guardrail = f"{invalidation_guardrail} 旧能力验证：{legacy_condition_notes['invalidation_note']}。"

    condition_items = [
        {"key": "add", "label": "加仓门槛", "text": add_guardrail, "tone": tone if status != "ready" else "success"},
        {"key": "reduce", "label": "减仓/降风险", "text": reduce_guardrail, "tone": "danger" if status == "blocked" else "warning"},
        {"key": "invalidation", "label": "失效门槛", "text": invalidation_guardrail, "tone": "danger" if status != "ready" else "warning"},
    ]
    return {
        "status": status,
        "tone": tone,
        "summary": summary,
        "group_highlights": _evidence_group_highlights(groups),
        "add_condition_guardrail": add_guardrail,
        "reduce_condition_guardrail": reduce_guardrail,
        "invalidation_guardrail": invalidation_guardrail,
        "legacy_condition_notes": legacy_condition_notes,
        "condition_items": condition_items,
        "deepseek_called": False,
    }


def _a_share_capability_state_from_readiness(readiness: str, summary: str = "") -> str:
    if any(key in readiness for key in ["阻断", "受限", "权限"]):
        return "blocked"
    if any(key in readiness for key in ["谨慎", "暂无数据", "缓存"]):
        return "cached"
    if any(key in readiness for key in ["待手动", "待检测", "待验证"]):
        return "missing"
    if any(key in readiness for key in ["可进入", "可用", "已可用"]):
        return "support"
    text = f"{readiness} {summary}"
    if any(key in text for key in ["阻断", "受限", "权限"]):
        return "blocked"
    if any(key in text for key in ["谨慎", "暂无数据", "缓存"]):
        return "cached"
    if any(key in text for key in ["待手动", "待检测", "待验证"]):
        return "missing"
    if any(key in text for key in ["可进入", "可用", "已可用"]):
        return "support"
    return "missing"


def _a_share_capability_action(label: str, state: str) -> str:
    if state == "blocked":
        return f"先处理 {label}；未恢复前策略只能降级为观察或小额试探。"
    if state == "cached":
        return f"复核 {label} 的日期和覆盖范围；不能把暂无数据当作无风险。"
    if state == "missing":
        return f"需要手动检测 {label}；页面打开不会自动请求 Tushare。"
    return f"{label}可进入证据链，但仍需和价格、纪律、仓位共振。"


def build_strategy_a_share_data_validation_items(a_share_data_console: Any = None) -> list[dict]:
    console = _as_mapping(a_share_data_console)
    if not console:
        return []

    readiness = _to_text(console.get("decision_readiness_label")) or _to_text(console.get("headline")) or "待检测"
    summary = _to_text(console.get("summary"))
    state = _a_share_capability_state_from_readiness(readiness, summary)
    items = [
        {
            "key": "a_share_data_capability",
            "label": "A股数据能力",
            "priority": 0,
            "evidence_state": state,
            "evidence_label": "数据能力",
            "tone": _evidence_validation_tone(state),
            "check_text": f"{readiness}｜{summary}" if summary else readiness,
            "action_hint": _a_share_capability_action("A股数据能力", state),
        }
    ]

    groups = {
        _to_text(group.get("key")): _as_mapping(group)
        for group in (console.get("groups") or [])
        if _as_mapping(group)
    }
    group_specs = [
        ("permission_denied", "受限数据", "blocked", 1),
        ("stale_or_empty", "暂无数据", "cached", 2),
        ("manual_required", "待手动刷新", "missing", 3),
        ("available", "可用数据", "support", 4),
    ]
    for key, label, group_state, priority in group_specs:
        group = groups.get(key) or {}
        count = _safe_int(group.get("count"))
        if count <= 0:
            continue
        names = _limited_text_join(group.get("items"), fallback=_to_text(group.get("summary")) or label)
        items.append(
            {
                "key": f"a_share_data_{key}",
                "label": label,
                "priority": priority,
                "evidence_state": group_state,
                "evidence_label": "数据能力",
                "tone": _evidence_validation_tone(group_state),
                "check_text": names,
                "action_hint": _a_share_capability_action(names, group_state),
            }
        )
        if len(items) >= 4:
            break
    return items


def build_strategy_a_share_data_validation_summary(a_share_data_console: Any = None) -> str:
    console = _as_mapping(a_share_data_console)
    if not console:
        return ""
    readiness = _to_text(console.get("decision_readiness_label")) or _to_text(console.get("headline")) or "待检测"
    summary = _to_text(console.get("summary"))
    return f"{readiness}｜{summary}" if summary else readiness


def _fact_recovery_group_text(items: list[dict], state: str, fallback: str) -> str:
    labels = [item["label"] for item in items if item.get("recovery_state") == state]
    return _limited_text_join(labels, fallback=fallback)


def _fact_recovery_state(blocked_text: str, waiting_text: str, recovered_text: str, blocked_count: int = 0, waiting_count: int = 0) -> str:
    if blocked_text or blocked_count:
        return "blocked"
    if waiting_text or waiting_count:
        return "missing"
    if recovered_text:
        return "support"
    return "missing"


def _fact_recovery_action(label: str, state: str) -> str:
    if state == "blocked":
        return f"先恢复受限事实：{label}；未恢复前策略只能降级为观察或小额试探。"
    if state == "missing":
        return f"先补齐待验证事实：{label}；缺失时不能把乐观路径当作加仓依据。"
    return f"已回流事实：{label}；仍需价格、纪律和仓位预算共振。"


def build_strategy_a_share_fact_recovery_validation_items(a_share_fact_recovery_summary: Any = None) -> list[dict]:
    summary = _as_mapping(a_share_fact_recovery_summary)
    if not summary:
        return []
    fact_items = []
    for raw in summary.get("items") or []:
        item = _as_mapping(raw)
        if not item:
            continue
        fact_items.append(
            {
                "label": _to_text(item.get("label")) or "A股事实",
                "recovery_state": _to_text(item.get("recovery_state")) or "waiting",
                "status_label": _to_text(item.get("status_label")) or "待验证",
            }
        )
    recovered_text = _fact_recovery_group_text(fact_items, "recovered", "")
    blocked_text = _fact_recovery_group_text(fact_items, "blocked", "")
    waiting_text = _fact_recovery_group_text(fact_items, "waiting", "")
    blocked_count = _safe_int(summary.get("blocked_count"))
    waiting_count = _safe_int(summary.get("waiting_count"))
    summary_text = _to_text(summary.get("summary"))
    if not summary_text:
        summary_text = (
            f"A股事实 {_safe_int(summary.get('total_count')) or 5} 项："
            f"已回流 {_safe_int(summary.get('recovered_count'))}"
            f"｜仍受限 {blocked_count}"
            f"｜待验证 {waiting_count}"
        )
    state = _fact_recovery_state(blocked_text, waiting_text, recovered_text, blocked_count, waiting_count)
    items = [
        {
            "key": "a_share_fact_recovery",
            "label": "A股事实回流",
            "priority": 0,
            "evidence_state": state,
            "evidence_label": "事实回流",
            "tone": _evidence_validation_tone(state),
            "check_text": summary_text,
            "action_hint": _fact_recovery_action(blocked_text or waiting_text or recovered_text or "五类事实", state),
        }
    ]
    group_specs = [
        ("blocked", "受限事实", blocked_text, 1),
        ("missing", "待验证事实", waiting_text, 2),
        ("support", "已回流事实", recovered_text, 4),
    ]
    for state_key, label, text, priority in group_specs:
        if not text:
            continue
        items.append(
            {
                "key": f"a_share_fact_recovery_{state_key}",
                "label": label,
                "priority": priority,
                "evidence_state": state_key,
                "evidence_label": "事实回流",
                "tone": _evidence_validation_tone(state_key),
                "check_text": text,
                "action_hint": _fact_recovery_action(text, state_key),
            }
        )
    return items[:4]


def build_strategy_a_share_fact_recovery_summary(a_share_fact_recovery_summary: Any = None) -> str:
    summary = _as_mapping(a_share_fact_recovery_summary)
    if not summary:
        return ""
    if _to_text(summary.get("summary")):
        return _to_text(summary.get("summary"))
    return (
        f"A股事实 {_safe_int(summary.get('total_count')) or 5} 项："
        f"已回流 {_safe_int(summary.get('recovered_count'))}"
        f"｜仍受限 {_safe_int(summary.get('blocked_count'))}"
        f"｜待验证 {_safe_int(summary.get('waiting_count'))}"
    )


def _fact_recovery_condition_tone(state: str) -> str:
    if state == "blocked":
        return "danger"
    if state == "partial":
        return "warning"
    if state == "ready":
        return "success"
    return "muted"


def _fact_recovery_group_highlights(fact_items: list[dict], summary: Mapping[str, Any]) -> list[dict]:
    specs = [
        ("blocked", "受限事实", "danger", _safe_int(summary.get("blocked_count"))),
        ("waiting", "待验证事实", "warning", _safe_int(summary.get("waiting_count"))),
        ("recovered", "已回流事实", "success", _safe_int(summary.get("recovered_count"))),
    ]
    highlights = []
    for state, label, tone, count_hint in specs:
        rows = [item for item in fact_items if item.get("recovery_state") == state]
        labels = [_to_text(item.get("label")) for item in rows if _to_text(item.get("label"))]
        root_causes = [_to_text(item.get("root_cause_label")) for item in rows if _to_text(item.get("root_cause_label"))]
        count = len(rows) or count_hint
        if count <= 0:
            continue
        value = _limited_text_join(labels, fallback="五类事实", limit=3)
        if root_causes and state != "recovered":
            value = f"{value}｜{_limited_text_join(root_causes, fallback='原因待确认', limit=2)}"
        highlights.append(
            {
                "key": f"a_share_fact_{state}",
                "label": label,
                "count": count,
                "value": value,
                "tone": tone,
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    return highlights


def build_strategy_a_share_fact_recovery_condition_guidance(
    a_share_fact_recovery_summary: Any = None,
    market_type: Any = None,
) -> dict:
    if _to_text(market_type) != "A股":
        return {}
    summary = _as_mapping(a_share_fact_recovery_summary)
    if not summary:
        return {}

    fact_items = []
    for raw in summary.get("items") or []:
        item = _as_mapping(raw)
        if not item:
            continue
        fact_items.append(
            {
                "label": _to_text(item.get("label")) or "A股事实",
                "recovery_state": _to_text(item.get("recovery_state")) or "waiting",
                "status_label": _to_text(item.get("status_label")) or "待验证",
                "root_cause_label": _to_text(item.get("root_cause_label")),
            }
        )
    highlights = _fact_recovery_group_highlights(fact_items, summary)
    blocked = next((item for item in highlights if item.get("key") == "a_share_fact_blocked"), {})
    waiting = next((item for item in highlights if item.get("key") == "a_share_fact_waiting"), {})
    recovered = next((item for item in highlights if item.get("key") == "a_share_fact_recovered"), {})
    blocked_text = _to_text(blocked.get("value")) or ("五类事实" if _safe_int(summary.get("blocked_count")) else "")
    waiting_text = _to_text(waiting.get("value")) or ("五类事实" if _safe_int(summary.get("waiting_count")) else "")
    recovered_text = _to_text(recovered.get("value")) or ("五类事实" if _safe_int(summary.get("recovered_count")) else "")
    summary_text = build_strategy_a_share_fact_recovery_summary(summary)

    if blocked_text:
        status = "blocked"
        add_guardrail = f"受限事实未恢复前，加仓门槛不得升级；先恢复 {blocked_text}，禁止追高、加融资或把缺口当作利好。"
        reduce_guardrail = f"若价格走弱且 {blocked_text} 无法排除，减仓/降风险优先于加仓。"
        invalidation_guardrail = f"{blocked_text} 持续受限时，本轮进攻假设失效，策略只能降级为观察或小额试探。"
    elif waiting_text:
        status = "partial"
        add_guardrail = f"待验证事实未回流前，加仓只能保持低置信度；先补齐 {waiting_text}。"
        reduce_guardrail = f"{waiting_text} 待验证时，如价格或纪律转弱，先减暴露、保现金。"
        invalidation_guardrail = f"{waiting_text} 无法回流或继续缺失时，本轮乐观执行条件不完整。"
    elif recovered_text:
        status = "ready"
        add_guardrail = f"已回流事实 {recovered_text} 可作为加仓辅助，但仍需 MA/量能/纪律和仓位预算共振。"
        reduce_guardrail = f"已回流事实若转弱或与价格纪律冲突，按纪律线减仓。"
        invalidation_guardrail = f"{recovered_text} 从支持转为分歧或失败时，本轮策略建议失效并重新生成。"
    else:
        status = "missing"
        add_guardrail = "A股事实回流总账待生成；加仓门槛保持待验证。"
        reduce_guardrail = "事实总账缺失且价格转弱时，先减暴露、保现金。"
        invalidation_guardrail = "A股事实总账无法确认时，本轮策略只保留观察。"

    tone = _fact_recovery_condition_tone(status)
    condition_items = [
        {"key": "add", "label": "加仓事实门槛", "text": add_guardrail, "tone": tone if status != "ready" else "success"},
        {"key": "reduce", "label": "减仓/降风险事实门槛", "text": reduce_guardrail, "tone": "danger" if status == "blocked" else "warning"},
        {"key": "invalidation", "label": "失效事实门槛", "text": invalidation_guardrail, "tone": "danger" if status != "ready" else "warning"},
    ]
    return {
        "status": status,
        "tone": tone,
        "summary": summary_text,
        "group_highlights": highlights,
        "add_condition_guardrail": add_guardrail,
        "reduce_condition_guardrail": reduce_guardrail,
        "invalidation_guardrail": invalidation_guardrail,
        "condition_items": condition_items,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _latest_recovery_evidence_state(status: str) -> str:
    if status == "recovered":
        return "support"
    if status == "blocked":
        return "blocked"
    return "missing"


def _latest_recovery_action(label: str, status: str) -> str:
    if status == "recovered":
        return f"{label}刚刚回流；可进入证据链，但仍需复核日期、来源和仓位纪律。"
    if status == "blocked":
        return f"{label}恢复仍受限；未解决前策略只能降级为观察或小额试探。"
    return f"{label}恢复结果待验证；不要把缺失事实当作加仓依据。"


def build_strategy_latest_recovery_validation_items(latest_recovery_result_notice: Any = None) -> list[dict]:
    notice = _as_mapping(latest_recovery_result_notice)
    if not notice:
        return []
    status = _to_text(notice.get("status")) or "waiting"
    state = _latest_recovery_evidence_state(status)
    label = _to_text(notice.get("label")) or "数据恢复"
    message = _to_text(notice.get("message")) or "已更新本地恢复状态。"
    return [
        {
            "key": "latest_recovery_result",
            "label": "最近恢复结果",
            "priority": 0,
            "evidence_state": state,
            "evidence_label": "恢复结果",
            "tone": _evidence_validation_tone(state),
            "check_text": f"{label}｜{message}",
            "action_hint": _latest_recovery_action(label, status),
            "writes_packet": _to_text(notice.get("writes_packet")),
            "external_call_policy": _to_text(notice.get("external_call_policy")) or "not_triggered",
        }
    ]


def build_strategy_latest_recovery_summary(latest_recovery_result_notice: Any = None) -> str:
    notice = _as_mapping(latest_recovery_result_notice)
    if not notice:
        return ""
    status = _to_text(notice.get("status")) or "waiting"
    label = _to_text(notice.get("label")) or "数据恢复"
    message = _to_text(notice.get("message")) or "已更新本地恢复状态。"
    return f"{label}：{status}｜{message}"


def _recovery_timeline_evidence_state(level: str, status: str = "") -> str:
    if level == "restored" or status == "recovered":
        return "support"
    if level in {"blocks_position_increase", "blocks_candidate_execution", "blocks_strategy_validation"} or status == "blocked":
        return "blocked"
    if level in {"requires_review", "confidence_only"} or status == "cached":
        return "cached"
    return "missing"


def _recovery_timeline_action(label: str, state: str, impact_label: str = "") -> str:
    if state == "blocked":
        return f"先处理 {label} 的{impact_label or '阻断影响'}；未恢复前策略条件不能升级为已验证。"
    if state == "cached":
        return f"复核 {label} 的缓存/置信度影响；执行前确认日期、来源和回流 packet。"
    if state == "support":
        return f"{label}已回流；可进入证据链，但仍需价格、纪律和仓位规则共同确认。"
    return f"{label}恢复影响待验证；不要把缺失旧工具能力当作策略已确认。"


def build_strategy_recovery_timeline_validation_items(recovery_result_timeline: Any = None) -> list[dict]:
    timeline = _as_mapping(recovery_result_timeline)
    if not timeline:
        return []
    items = [_as_mapping(item) for item in _as_list(timeline.get("items")) if _as_mapping(item)]
    result = []
    for raw in items[:3]:
        label = _to_text(raw.get("label")) or "旧工具恢复"
        level = _to_text(raw.get("decision_impact_level"))
        impact_label = _to_text(raw.get("decision_impact_label")) or "恢复影响"
        state = _recovery_timeline_evidence_state(level, _to_text(raw.get("status")))
        result.append(
            {
                "key": f"recovery_timeline:{_to_text(raw.get('writes_packet')) or label}",
                "label": f"旧恢复影响：{label}",
                "priority": 0,
                "evidence_state": state,
                "evidence_label": impact_label,
                "tone": _evidence_validation_tone(state),
                "check_text": _to_text(raw.get("decision_impact_text")) or _to_text(raw.get("message")) or "恢复影响待验证。",
                "action_hint": _recovery_timeline_action(label, state, impact_label),
                "writes_packet": _to_text(raw.get("writes_packet")),
                "decision_impact_level": level,
                "external_call_policy": _to_text(raw.get("external_call_policy")) or "not_triggered",
                "deepseek_called": False,
            }
        )
    if not result and _to_text(timeline.get("decision_impact_summary")):
        result.append(
            {
                "key": "recovery_timeline_summary",
                "label": "旧工具恢复影响",
                "priority": 0,
                "evidence_state": _recovery_timeline_evidence_state("", _to_text(timeline.get("status"))),
                "evidence_label": _to_text(timeline.get("headline")) or "恢复影响",
                "tone": _evidence_validation_tone(_recovery_timeline_evidence_state("", _to_text(timeline.get("status")))),
                "check_text": _to_text(timeline.get("decision_impact_summary")),
                "action_hint": _to_text(timeline.get("next_action")) or "按恢复队列手动处理旧工具能力。",
                "external_call_policy": _to_text(timeline.get("external_call_policy")) or "not_triggered",
                "deepseek_called": False,
            }
        )
    return result


def build_strategy_recovery_timeline_summary(recovery_result_timeline: Any = None) -> str:
    timeline = _as_mapping(recovery_result_timeline)
    if not timeline:
        return ""
    summary = _to_text(timeline.get("decision_impact_summary")) or _to_text(timeline.get("summary"))
    if not summary:
        return ""
    items = [_as_mapping(item) for item in _as_list(timeline.get("items")) if _as_mapping(item)]
    blockers = [
        _to_text(item.get("label"))
        for item in items
        if _to_text(item.get("decision_impact_level")) in {
            "blocks_position_increase",
            "blocks_candidate_execution",
            "blocks_strategy_validation",
        }
    ]
    if blockers:
        return f"{summary}｜阻断：{'、'.join([item for item in blockers if item][:2])}"
    return summary


def build_strategy_evidence_validation_items(
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    market_type: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
    recovery_result_timeline: Any = None,
) -> list[dict]:
    evidence = _as_mapping(evidence_radar_packet)
    items = build_strategy_a_share_data_validation_items(a_share_data_console)
    health_impact = build_data_health_impact_summary(data_health_ledger, market_type=market_type)
    if health_impact.get("status") != "missing":
        items.append(
            {
                "key": "data_health_ledger",
                "label": "接口健康账本",
                "priority": 0,
                "evidence_state": "blocked" if health_impact["status"] == "blocked" else "cached" if health_impact["status"] == "partial" else "support",
                "evidence_label": health_impact["label"],
                "tone": health_impact["tone"],
                "check_text": health_impact["summary"],
                "action_hint": health_impact["strategy_action"],
            }
        )
    items.extend(build_strategy_a_share_fact_recovery_validation_items(a_share_fact_recovery_summary))
    items.extend(build_strategy_latest_recovery_validation_items(latest_recovery_result_notice))
    items.extend(build_strategy_recovery_timeline_validation_items(recovery_result_timeline))
    queue = evidence.get("decision_evidence_queue") or []
    if not isinstance(queue, list):
        queue = []
    if not queue:
        queue = (
            list(evidence.get("blocker_items") or [])
            + list(evidence.get("missing_items") or [])
            + list(evidence.get("cached_items") or [])
            + list(evidence.get("support_items") or [])
        )
    for raw in queue:
        item = _as_mapping(raw)
        if not item:
            continue
        evidence_state = _to_text(item.get("evidence_state")) or "missing"
        label = _to_text(item.get("label")) or "A股证据"
        items.append(
            {
                "key": _to_text(item.get("key")) or "a_share_evidence",
                "label": label,
                "priority": item.get("priority") or 3,
                "evidence_state": evidence_state,
                "evidence_label": _to_text(item.get("evidence_label")) or "待验证证据",
                "tone": _evidence_validation_tone(evidence_state),
                "check_text": _to_text(item.get("decision_signal")) or _evidence_validation_action(label, evidence_state),
                "action_hint": _evidence_validation_action(label, evidence_state),
            }
        )
        if len(items) >= 6:
            break
    if not items:
        return [
            {
                "key": "a_share_evidence_missing",
                "label": "A股证据雷达",
                "priority": 1,
                "evidence_state": "missing",
                "evidence_label": "缺失证据",
                "tone": "warning",
                "check_text": "A股证据雷达尚未生成；策略执行只能作为待验证路径。",
                "action_hint": "先刷新今日基础数据或手动检测关键 A股能力。",
            }
        ]
    return items


def _data_status_label(value: Any) -> str:
    state = _to_text(value).lower() or "missing"
    return DATA_STATUS_STATE_LABELS.get(state, _to_text(value) or "待刷新")


def strategy_readiness_text(packet: Any) -> str:
    payload = _as_mapping(packet)
    status = normalize_strategy_status(payload)
    if status == "waiting" or not payload:
        return "待刷新：点击“生成策略执行建议”后，读取已有量化/纪律缓存生成。"
    missing = [
        item["label"]
        for item in build_strategy_data_status_items(payload)
        if item["state"] in {"missing", "failed", "waiting"}
    ]
    if missing:
        return f"数据不足：{ '、'.join(missing) } 待刷新，当前只能作为谨慎路径。"
    if payload.get("stale"):
        return "使用缓存：上次成功结果仍可查看，但需要重新验证。"
    return "可读结论：已基于当前缓存生成，执行前仍需核对价格与纪律线。"


def _warning_items(packet: Mapping[str, Any]) -> list[str]:
    discipline = _as_mapping(packet.get("discipline_check"))
    warnings = [_to_text(item) for item in (discipline.get("warnings") or packet.get("warnings") or [])]
    warnings = [item for item in warnings if item]
    errors = packet.get("errors") or []
    if isinstance(errors, (list, tuple)):
        for item in errors[:3]:
            payload = _as_mapping(item)
            if payload:
                warnings.append(f"{_to_text(payload.get('module')) or '模块'}：{_to_text(payload.get('message') or payload.get('error')) or '未知错误'}")
            else:
                text = _to_text(item)
                if text:
                    warnings.append(text)
    if packet.get("stale"):
        warnings.append("当前展示为上次成功结果。")
    if packet.get("last_error"):
        warnings.append(f"上次生成失败：{_to_text(packet.get('last_error'))}")
    if packet.get("last_success") and not packet.get("stale"):
        warnings.append("已有上次成功结果可回退。")
    return warnings[:6] or ["暂无新增异常；仍需遵守不追高、不自动重仓。"]


def build_strategy_summary_view_model(
    packet: Any,
    analysis_method_packet: Any = None,
    projection_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
    recovery_result_timeline: Any = None,
) -> dict:
    payload = _as_mapping(packet)
    is_empty = not bool(payload)
    action = "尚未生成" if is_empty else strategy_action_label(payload)
    confidence = "待生成" if is_empty else (_to_text(payload.get("confidence")) or "低")
    summary = _to_text(payload.get("summary")) or "尚未生成策略执行建议。点击按钮后只读取缓存、量化摘要和纪律结果，不调用 DeepSeek，不跑回测。"
    market_guidance = build_market_method_guidance(analysis_method_packet)
    market_type = _to_text(_as_mapping(analysis_method_packet).get("market"))
    evidence_validation_items = build_strategy_evidence_validation_items(
        evidence_radar_packet,
        a_share_data_console=a_share_data_console,
        data_health_ledger=data_health_ledger,
        market_type=market_type,
        a_share_fact_recovery_summary=a_share_fact_recovery_summary,
        latest_recovery_result_notice=latest_recovery_result_notice,
        recovery_result_timeline=recovery_result_timeline,
    )
    a_share_data_validation_summary = build_strategy_a_share_data_validation_summary(a_share_data_console)
    a_share_fact_recovery_validation_summary = build_strategy_a_share_fact_recovery_summary(a_share_fact_recovery_summary)
    latest_recovery_validation_summary = build_strategy_latest_recovery_summary(latest_recovery_result_notice)
    recovery_timeline_validation_summary = build_strategy_recovery_timeline_summary(recovery_result_timeline)
    evidence_radar_card = _as_mapping(_as_mapping(evidence_radar_packet).get("radar_card"))
    projection_confidence = build_projection_confidence_summary(projection_packet)
    evidence_group_guidance = build_strategy_a_share_evidence_group_guidance(evidence_radar_packet)
    fact_recovery_condition_guidance = build_strategy_a_share_fact_recovery_condition_guidance(
        a_share_fact_recovery_summary,
        market_type=market_type,
    )
    return {
        "status": normalize_strategy_status(payload),
        "status_label": strategy_status_label(payload),
        "status_tone": strategy_status_tone(payload),
        "action_label": action,
        "action_tone": strategy_action_tone({"action": action}),
        "confidence_label": confidence,
        "confidence_tone": strategy_confidence_tone({"confidence": confidence}),
        "summary": summary,
        "action_guardrail": strategy_action_guardrail_text({"action": action}),
        "readiness_text": strategy_readiness_text(payload),
        "user_boundary_text": strategy_user_boundary_text(payload),
        "position_advice": _to_text(payload.get("position_advice")) or "等待策略执行建议补齐。",
        "conditions": build_strategy_condition_items(payload),
        "condition_items": build_strategy_condition_cards(payload),
        "path_items": build_strategy_path_items(payload),
        "discipline_items": build_strategy_discipline_items(payload),
        "risk_budget_items": build_strategy_risk_budget_items(payload),
        "data_status_items": build_strategy_data_status_items(payload),
        "warning_items": _warning_items(payload),
        "market_method_guidance": market_guidance,
        "projection_confidence_summary": projection_confidence,
        "evidence_radar_card": evidence_radar_card,
        "evidence_confidence_gate": _to_text(evidence_radar_card.get("confidence_gate")) or "不可验证",
        "evidence_execution_guardrail": _to_text(evidence_radar_card.get("execution_guardrail")),
        "evidence_validation_items": evidence_validation_items,
        "a_share_evidence_group_guidance": evidence_group_guidance,
        "a_share_fact_recovery_condition_guidance": fact_recovery_condition_guidance,
        "data_health_impact": build_data_health_impact_summary(data_health_ledger, market_type=market_type),
        "evidence_validation_summary": _to_text(_as_mapping(evidence_radar_packet).get("decision_summary")) or "支持 0｜阻断 0｜缓存 0｜缺失 0",
        "a_share_data_validation_summary": a_share_data_validation_summary,
        "a_share_fact_recovery_validation_summary": a_share_fact_recovery_validation_summary,
        "latest_recovery_validation_summary": latest_recovery_validation_summary,
        "recovery_timeline_validation_summary": recovery_timeline_validation_summary,
        "risk_label": _to_text(_as_mapping(payload.get("risk_budget")).get("risk_level")) or "未知",
        "deepseek_text": "DeepSeek：已调用" if bool(payload.get("deepseek_called")) else "DeepSeek：未调用",
        "updated_text": _to_text(payload.get("updated_at")) or "暂无",
        "source_text": _to_text(payload.get("source")) or "strategy_execution_service / session_state cache",
        "last_error_text": _to_text(payload.get("last_error")),
        "empty_message": "尚未生成策略执行建议。",
    }
