from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


EVIDENCE_DEFS = (
    (
        "moneyflow_packet",
        "moneyflow",
        "个股资金流",
        "flow_state",
        ("five_day_main_net_yi", "main_net_yi"),
        "亿",
        1,
        "验证资金是否支持当前动作。",
    ),
    (
        "hard_risk_packet",
        "hard_risk",
        "公告/硬风险",
        "risk_state",
        ("risk_item_count",),
        "项",
        1,
        "排查公告、减持、质押、解禁等硬风险阻断。",
    ),
    (
        "margin_packet",
        "margin",
        "融资融券",
        "leverage_state",
        ("financing_buy_yi", "financing_balance_yi"),
        "亿",
        2,
        "观察杠杆变化和融资风险预算。",
    ),
    (
        "limit_emotion_packet",
        "limit_emotion",
        "涨跌停/情绪",
        "emotion_state",
        ("distance_to_up_pct", "up_limit"),
        "",
        2,
        "识别过热、追高和情绪边界。",
    ),
    (
        "dragon_tiger_packet",
        "dragon_tiger",
        "龙虎榜",
        "activity_state",
        ("net_buy_amount_yi",),
        "亿",
        3,
        "识别席位行为和短线情绪线索。",
    ),
    (
        "chip_packet",
        "chip_radar",
        "筹码/胜率",
        "pressure_state",
        ("winner_rate",),
        "%",
        3,
        "验证压力位、筹码结构和胜率口径。",
    ),
)


EVIDENCE_ACTIONS = {
    "moneyflow": {
        "button_label": "手动刷新个股资金流",
        "toolbox_entry": "高级工具箱 / A股专业实盘 / 个股资金流",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_moneyflow_packet",
    },
    "hard_risk": {
        "button_label": "检测公告/硬风险",
        "toolbox_entry": "高级工具箱 / 天眼风控 / A股公告风险",
        "legacy_tab": "天眼风控",
        "writes_packet": "command_center_hard_risk_packet",
    },
    "margin": {
        "button_label": "手动刷新融资融券",
        "toolbox_entry": "高级工具箱 / 融资 ETF / 融资融券",
        "legacy_tab": "融资 ETF",
        "writes_packet": "command_center_margin_packet",
    },
    "limit_emotion": {
        "button_label": "手动刷新涨跌停/情绪",
        "toolbox_entry": "高级工具箱 / 数据源体检 / 涨跌停情绪",
        "legacy_tab": "数据源体检",
        "writes_packet": "command_center_limit_emotion_packet",
    },
    "dragon_tiger": {
        "button_label": "手动刷新龙虎榜",
        "toolbox_entry": "高级工具箱 / 下一票雷达 / 龙虎榜",
        "legacy_tab": "下一票雷达",
        "writes_packet": "command_center_dragon_tiger_packet",
    },
    "chip_radar": {
        "button_label": "手动刷新筹码/胜率",
        "toolbox_entry": "高级工具箱 / 量化推演 / 筹码胜率",
        "legacy_tab": "量化推演",
        "writes_packet": "command_center_chip_packet",
    },
}


WRITES_PACKET_TO_EVIDENCE_KEY = {
    config["writes_packet"]: key
    for key, config in EVIDENCE_ACTIONS.items()
    if config.get("writes_packet")
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def to_number(value: Any) -> int | float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Number):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "").replace("亿", "")
        if not text or text in {"--", "暂无", "N/A", "None", "nan"}:
            return None
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except Exception:
            return None
    return None


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _first_number(packet: Mapping[str, Any], keys: tuple[str, ...]) -> int | float | None:
    for key in keys:
        number = to_number(packet.get(key))
        if number is not None:
            return number
    return None


def _status_label(status: str, data_status: str) -> str:
    if status == "failed":
        return "失败/受限"
    if data_status == "ready":
        return "已刷新"
    if data_status == "cached":
        return "使用缓存"
    return "待验证"


def _status_tone(status: str, data_status: str) -> str:
    if status == "failed":
        return "failed"
    if data_status == "ready":
        return "ready"
    if data_status == "cached":
        return "stale"
    return "missing"


def _evidence_state(status: str, data_status: str) -> str:
    if status == "failed":
        return "blocked"
    if data_status == "ready":
        return "supporting"
    if data_status == "cached":
        return "cached"
    return "missing"


def _evidence_label(evidence_state: str) -> str:
    return {
        "supporting": "支持证据",
        "blocked": "阻断证据",
        "cached": "缓存证据",
        "missing": "缺失证据",
    }.get(evidence_state, "待验证证据")


def _decision_signal(label: str, headline: str, evidence_state: str) -> str:
    if evidence_state == "supporting":
        return f"{label}已刷新，可辅助验证：{headline}"
    if evidence_state == "blocked":
        return f"{label}失败/受限，不能支撑加仓或放大仓位。"
    if evidence_state == "cached":
        return f"{label}使用缓存，执行前必须复核日期和口径。"
    return f"{label}待验证，当前不进入核心决策依据。"


def _evidence_action_hint(label: str, evidence_state: str) -> str:
    if evidence_state == "blocked":
        return f"先确认{label}是否权限不足、接口失败或本会话跳过；未恢复前不要把缺失写成利好。"
    if evidence_state == "cached":
        return f"交易前复核{label}交易日和更新时间；需要最新口径时手动刷新。"
    if evidence_state == "missing":
        return f"点击对应入口手动补齐{label}，补齐前只作为待验证证据。"
    return f"{label}已可辅助验证，仍需和价格纪律、仓位规则一起看。"


def _join_labels(items: Any, limit: int = 3, fallback: str = "暂无") -> str:
    labels = [to_text(as_mapping(item).get("label")) for item in as_list(items)]
    labels = [label for label in labels if label]
    if not labels:
        return fallback
    suffix = f" 等 {len(labels)} 项" if len(labels) > limit else ""
    return "、".join(labels[:limit]) + suffix


def _short_decision_signals(items: Any, limit: int = 3) -> list[str]:
    signals = []
    for raw in as_list(items):
        item = as_mapping(raw)
        text = to_text(item.get("decision_signal")) or to_text(item.get("next_action")) or to_text(item.get("headline"))
        if text:
            signals.append(text)
        if len(signals) >= limit:
            break
    return signals


def build_recovered_evidence_modules(support_items: Any = None, limit: int = 4) -> list[dict]:
    modules = []
    for raw in as_list(support_items):
        item = as_mapping(raw)
        if not item:
            continue
        modules.append(
            {
                "key": to_text(item.get("key"), "a_share_evidence"),
                "label": to_text(item.get("label"), "A股证据"),
                "headline": to_text(item.get("headline"), "已回流"),
                "metric": to_text(item.get("metric"), "暂无数值"),
                "decision_role": to_text(item.get("decision_role"), "辅助验证。"),
                "decision_signal": to_text(item.get("decision_signal"), "已回流，可辅助验证。"),
                "source": to_text(item.get("source"), "本地 packet"),
                "updated_at": to_text(item.get("updated_at"), "暂无时间"),
                "writes_packet": to_text(as_mapping(item.get("manual_action")).get("writes_packet")),
                "deepseek_called": False,
            }
        )
        if len(modules) >= max(1, int(limit or 4)):
            break
    return modules


def recovered_evidence_summary_text(support_items: Any = None) -> str:
    modules = build_recovered_evidence_modules(support_items)
    if not modules:
        return "暂无已回流 A股证据模块"
    labels = [item["label"] for item in modules if item.get("label")]
    return "已回流：" + "、".join(labels[:4])


def build_latest_recovery_evidence_impact(latest_recovery_result_notice: Any = None) -> dict:
    notice = as_mapping(latest_recovery_result_notice)
    if not notice:
        return {}
    status = to_text(notice.get("status"), "waiting")
    label = to_text(notice.get("label"), "数据恢复")
    writes_packet = to_text(notice.get("writes_packet"))
    evidence_key = WRITES_PACKET_TO_EVIDENCE_KEY.get(writes_packet, "")
    message = to_text(notice.get("message"), "已更新本地恢复状态。")
    if status == "recovered":
        evidence_state = "supporting"
        tone = "ready"
        impact_text = f"{label}刚刚回流；可进入证据链，但执行前仍需复核交易日、来源和仓位纪律。"
        action_hint = "返回综合推演中心查看 Home Action Snapshot；不要把单项恢复写成自动加仓。"
    elif status == "blocked":
        evidence_state = "blocked"
        tone = "failed"
        impact_text = f"{label}恢复仍受限；证据门槛维持阻断，不能把缺失数据当成利好。"
        action_hint = "先处理权限、积分、交易日、网络或覆盖范围问题；策略保持观察/降风险。"
    else:
        evidence_state = "missing"
        tone = "missing"
        impact_text = f"{label}恢复结果待验证；尚不能进入核心证据链。"
        action_hint = "在高级工具箱对应模块手动运行后，再回到综合推演中心查看回流状态。"
    return {
        "key": "latest_recovery_result",
        "evidence_key": evidence_key,
        "label": label,
        "status": status,
        "evidence_state": evidence_state,
        "tone": tone,
        "impact_text": impact_text,
        "action_hint": action_hint,
        "message": message,
        "writes_packet": writes_packet,
        "updated_at": to_text(notice.get("updated_at")),
        "source": to_text(notice.get("source"), "最近恢复结果"),
        "external_call_policy": to_text(notice.get("external_call_policy"), "not_triggered"),
        "deepseek_called": False,
    }


def build_evidence_radar_card_view_model(
    support_items: Any = None,
    blocker_items: Any = None,
    cached_items: Any = None,
    missing_items: Any = None,
    latest_recovery_impact: Any = None,
) -> dict:
    support = as_list(support_items)
    blockers = as_list(blocker_items)
    cached = as_list(cached_items)
    missing = as_list(missing_items)
    support_count = len(support)
    blocker_count = len(blockers)
    cached_count = len(cached)
    missing_count = len(missing)
    latest_impact = as_mapping(latest_recovery_impact)
    latest_state = to_text(latest_impact.get("evidence_state"))
    if latest_state == "blocked" and not blocker_count:
        blocker_count = 1
    if latest_state == "supporting" and not support_count:
        support_count = 1
    if latest_state == "missing" and not missing_count:
        missing_count = 1
    blocker_text_items = blockers or ([latest_impact] if latest_state == "blocked" else [])
    recovery_text_items = blockers + cached + missing
    if latest_state in {"blocked", "missing"} and latest_impact:
        recovery_text_items = [latest_impact] + recovery_text_items
    support_text_items = support or ([latest_impact] if latest_state == "supporting" else [])
    if blocker_count:
        status = "blocked"
        status_label = "阻断加仓"
        tone = "danger"
        confidence_gate = "低置信度"
        execution_guardrail = (
            f"先处理{_join_labels(blocker_text_items, fallback='阻断证据')}；未排除前不能把缺失数据写成利好，"
            "策略只能观察、降风险或小额试探。"
        )
    elif cached_count or missing_count:
        status = "partial"
        status_label = "谨慎验证"
        tone = "warning"
        confidence_gate = "中低置信度"
        recovery = _join_labels(recovery_text_items, fallback="缓存/缺失证据")
        execution_guardrail = f"{recovery}仍需复核；未补齐前不要追高、满仓或加融资。"
    elif support_count:
        status = "ready"
        status_label = "可进入证据链"
        tone = "success"
        confidence_gate = "可验证"
        execution_guardrail = "关键 A股证据已形成支持链，但仍需价格纪律、仓位预算和失效条件共同确认。"
    else:
        status = "missing"
        status_label = "待刷新"
        tone = "muted"
        confidence_gate = "不可验证"
        execution_guardrail = "A股证据雷达尚未生成；只能显示空态或上次缓存，不支撑交易动作。"
    if latest_impact:
        impact_text = to_text(latest_impact.get("impact_text"))
        if impact_text:
            execution_guardrail = f"{execution_guardrail} 最近恢复：{impact_text}"
    return {
        "status": status,
        "status_label": status_label,
        "tone": tone,
        "confidence_gate": confidence_gate,
        "summary": f"支持 {support_count}｜阻断 {blocker_count}｜缓存 {cached_count}｜缺失 {missing_count}",
        "top_supports": [as_mapping(item) for item in support[:3]],
        "primary_blockers": [as_mapping(item) for item in blockers[:3]],
        "required_recovery": [as_mapping(item) for item in (blockers + cached + missing)[:4]],
        "support_text": _join_labels(support_text_items, fallback="暂无支持证据"),
        "blocker_text": _join_labels(blocker_text_items, fallback="暂无阻断证据"),
        "recovery_text": _join_labels(recovery_text_items, fallback="暂无待补证据"),
        "decision_guardrail": execution_guardrail,
        "execution_guardrail": execution_guardrail,
        "decision_signals": _short_decision_signals(blockers + cached + missing + support),
        "latest_recovery_impact": latest_impact,
        "manual_note": "证据雷达只读取本地 packet；所有补齐动作都必须手动触发。",
        "deepseek_called": False,
    }


def _manual_action(key: str, label: str, evidence_state: str) -> dict:
    config = EVIDENCE_ACTIONS.get(key, {})
    writes_packet = to_text(config.get("writes_packet"), f"command_center_{key}_packet")
    legacy_tab = to_text(config.get("legacy_tab"), "数据源体检")
    return {
        "button_label": to_text(config.get("button_label"), f"手动刷新{label}"),
        "toolbox_entry": to_text(config.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "writes_packet": writes_packet,
        "refresh_policy": "button_gated",
        "reason": _evidence_action_hint(label, evidence_state),
        "source_label": "A股证据雷达",
        "deepseek_called": False,
    }


def _format_metric(key: str, value: int | float | None, suffix: str) -> str:
    if value is None:
        return "暂无数值"
    if key == "limit_emotion":
        if suffix:
            return f"{value:+.2f}{suffix}"
        return f"{value:.2f}"
    if suffix == "%":
        return f"{value:.2f}%"
    if suffix == "亿":
        return f"{value:+.2f}亿"
    if suffix == "项":
        return f"{int(value)}项" if float(value).is_integer() else f"{value}项"
    return f"{value}"


def _risk_text(packet: Mapping[str, Any]) -> str:
    notes = [to_text(item) for item in as_list(packet.get("risk_notes"))]
    notes = [item for item in notes if item]
    return notes[0] if notes else _first_text(packet.get("manual_required_text"), packet.get("summary"), default="待验证，不能单独作为交易依据。")


def build_evidence_item(
    packet: Any,
    *,
    key: str,
    label: str,
    headline_key: str,
    metric_keys: tuple[str, ...],
    metric_suffix: str = "",
    priority: int = 3,
    decision_role: str = "",
) -> dict:
    payload = as_mapping(packet)
    status = to_text(payload.get("status"), "waiting")
    data_status = to_text(payload.get("data_status"), "missing")
    metric = _first_number(payload, metric_keys)
    headline = _first_text(
        payload.get(headline_key),
        payload.get("summary"),
        default="待验证" if data_status == "missing" else "已读取",
    )
    evidence_state = _evidence_state(status, data_status)
    label_text = to_text(label, "A股证据")
    return {
        "key": key,
        "label": label_text,
        "priority": priority,
        "decision_role": decision_role,
        "status": status,
        "data_status": data_status,
        "evidence_state": evidence_state,
        "evidence_label": _evidence_label(evidence_state),
        "status_label": _status_label(status, data_status),
        "tone": _status_tone(status, data_status),
        "headline": headline,
        "metric": _format_metric(key, metric, metric_suffix),
        "decision_signal": _decision_signal(label, headline, evidence_state),
        "source": _first_text(payload.get("source"), payload.get("api"), default="本地缓存"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("trade_date"), default="暂无时间"),
        "risk_text": _risk_text(payload),
        "manual_required_text": _first_text(payload.get("manual_required_text"), default="缺失时需要手动刷新或权限校验。"),
        "next_action": _evidence_action_hint(label_text, evidence_state),
        "manual_action": _manual_action(key, label_text, evidence_state),
        "deepseek_called": False,
    }


def build_a_share_evidence_radar_view_model(snapshot: Any = None) -> dict:
    payload = as_mapping(snapshot)
    items = [
        build_evidence_item(
            payload.get(packet_key),
            key=key,
            label=label,
            headline_key=headline_key,
            metric_keys=metric_keys,
            metric_suffix=suffix,
            priority=priority,
            decision_role=decision_role,
        )
        for packet_key, key, label, headline_key, metric_keys, suffix, priority, decision_role in EVIDENCE_DEFS
    ]
    ready = [item for item in items if item["data_status"] == "ready"]
    cached = [item for item in items if item["data_status"] == "cached"]
    failed = [item for item in items if item["status"] == "failed"]
    missing = [item for item in items if item["data_status"] == "missing" and item["status"] != "failed"]
    support_items = [item for item in items if item["evidence_state"] == "supporting"]
    blocker_items = [item for item in items if item["evidence_state"] == "blocked"]
    cached_items = [item for item in items if item["evidence_state"] == "cached"]
    missing_items = [item for item in items if item["evidence_state"] == "missing"]
    decision_evidence_queue = sorted(
        items,
        key=lambda item: (
            item["priority"],
            {"blocked": 0, "missing": 1, "cached": 2, "supporting": 3}.get(item["evidence_state"], 4),
            item["label"],
        ),
    )
    next_evidence_actions = [
        {
            "key": item["key"],
            "label": item["label"],
            "priority": item["priority"],
            "evidence_state": item["evidence_state"],
            "evidence_label": item["evidence_label"],
            "status_label": item["status_label"],
            "tone": item["tone"],
            "action_hint": item["next_action"],
            "manual_action": item["manual_action"],
            "action_label": item["manual_action"]["button_label"],
            "toolbox_entry": item["manual_action"]["toolbox_entry"],
            "workspace_target": item["manual_action"]["workspace_target"],
            "workspace_state_key": item["manual_action"]["workspace_state_key"],
            "legacy_tab": item["manual_action"]["legacy_tab"],
            "legacy_tab_state_key": item["manual_action"]["legacy_tab_state_key"],
            "navigation_label": item["manual_action"]["navigation_label"],
            "writes_packet": item["manual_action"]["writes_packet"],
            "refresh_policy": item["manual_action"]["refresh_policy"],
            "source_label": "A股证据雷达",
            "decision_role": item["decision_role"],
            "deepseek_called": False,
        }
        for item in decision_evidence_queue
        if item["evidence_state"] != "supporting"
    ]
    summary = (
        f"已刷新 {len(ready)} 项｜使用缓存 {len(cached)} 项｜失败/受限 {len(failed)} 项｜待验证 {len(missing)} 项"
    )
    decision_summary = (
        f"支持 {len(support_items)}｜阻断 {len(blocker_items)}｜缓存 {len(cached_items)}｜缺失 {len(missing_items)}"
    )
    latest_recovery_impact = build_latest_recovery_evidence_impact(payload.get("latest_recovery_result_notice"))
    recovered_modules = build_recovered_evidence_modules(support_items)
    radar_card = build_evidence_radar_card_view_model(
        support_items=support_items,
        blocker_items=blocker_items,
        cached_items=cached_items,
        missing_items=missing_items,
        latest_recovery_impact=latest_recovery_impact,
    )
    return {
        "title": "A股证据雷达",
        "summary": summary,
        "decision_summary": decision_summary,
        "radar_card": radar_card,
        "latest_recovery_impact": latest_recovery_impact,
        "recovered_evidence_modules": recovered_modules,
        "recovered_evidence_summary": recovered_evidence_summary_text(support_items),
        "items": items,
        "support_items": support_items,
        "blocker_items": blocker_items,
        "cached_items": cached_items,
        "missing_items": missing_items,
        "decision_evidence_queue": decision_evidence_queue,
        "next_evidence_actions": next_evidence_actions,
        "ready_count": len(ready),
        "cached_count": len(cached),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "manual_note": "证据雷达只读取本地 packet；页面打开不会自动请求 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


def build_home_evidence_backfill_actions(
    evidence_radar_packet: Any = None,
    runnable_keys: Any = None,
    limit: int = 2,
) -> list[dict]:
    packet = as_mapping(evidence_radar_packet)
    if isinstance(runnable_keys, (set, frozenset)):
        raw_keys = list(runnable_keys)
    else:
        raw_keys = as_list(runnable_keys)
    allowed = {to_text(key) for key in raw_keys}
    if not allowed:
        allowed = set(EVIDENCE_ACTIONS)
    result = []
    for raw in as_list(packet.get("next_evidence_actions")):
        item = as_mapping(raw)
        key = to_text(item.get("key"))
        manual_action = as_mapping(item.get("manual_action"))
        if not key or key not in allowed:
            continue
        if manual_action.get("refresh_policy") != "button_gated":
            continue
        result.append({**item, "manual_action": manual_action, "deepseek_called": False})
        if len(result) >= max(1, int(limit or 2)):
            break
    return result


def build_home_evidence_recovery_summary(
    evidence_radar_packet: Any = None,
    runnable_keys: Any = None,
    limit: int = 2,
) -> dict:
    actions = build_home_evidence_backfill_actions(
        evidence_radar_packet,
        runnable_keys=runnable_keys,
        limit=limit,
    )
    if not actions:
        return {
            "status": "ready",
            "title": "数据恢复建议",
            "summary": "关键 A股证据暂不需要手动补齐；继续以价格纪律、仓位规则和已验证 packet 为准。",
            "actions": [],
            "deepseek_called": False,
        }
    labels = [to_text(item.get("label")) for item in actions]
    labels = [label for label in labels if label]
    packet_names = [
        to_text(as_mapping(item.get("manual_action")).get("writes_packet"))
        for item in actions
    ]
    packet_names = [name for name in packet_names if name]
    first_action = as_mapping(actions[0].get("manual_action"))
    first_label = labels[0] if labels else "关键证据"
    return {
        "status": "needs_recovery",
        "title": "数据恢复建议｜补齐关键 A股证据",
        "summary": (
            f"优先补齐：{'、'.join(labels)}。先点「{to_text(first_action.get('button_label'), '手动刷新')}」；"
            f"结果会回流到 {'、'.join(packet_names)}，页面不会自动调用 DeepSeek 或全市场扫描。"
        ),
        "primary_label": first_label,
        "primary_button_label": to_text(first_action.get("button_label"), "手动刷新"),
        "actions": actions,
        "deepseek_called": False,
    }
