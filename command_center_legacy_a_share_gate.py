from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import market_data_capability as data_capability_service


SECTION_SPECS = {
    "dragon_tiger": ("龙虎榜", "top_list/top_inst", "龙虎榜按当前标的 TTL 自动检测；强制刷新可绕过 TTL。"),
    "margin": ("融资融券", "margin_detail", "融资融券按当前标的 TTL 自动检测；强制刷新可绕过 TTL。"),
    "moneyflow": ("个股资金流", "moneyflow", "个股资金流按当前标的 TTL 自动检测；强制刷新可绕过 TTL。"),
    "limit_emotion": (
        "涨跌停/情绪",
        "stk_limit / limit_list_d / limit_cpt_list",
        "涨跌停/情绪按当前标的 TTL 自动检测；强制刷新可绕过 TTL。",
    ),
    "chip_radar": ("筹码/胜率", "cyq_perf/cyq_chips", "筹码/胜率按当前标的 TTL 自动检测；强制刷新可绕过 TTL。"),
}

REFRESH_CAPTION = "本页会按当前标的 TTL 自动请求必要 Tushare 专业接口；强制刷新会清除本页相关缓存并立即重检。"
EMPTY_NOTICE = "未检测到 A股专业事实缓存；页面会按当前标的自动检测必要 Tushare 专业接口，失败会保留缓存/空态。"

AVAILABLE_STATES = {data_capability_service.STATE_AVAILABLE}
RESTRICTED_STATES = {
    data_capability_service.STATE_PERMISSION_DENIED,
    data_capability_service.STATE_DISABLED_THIS_SESSION,
    data_capability_service.STATE_NETWORK_FAILED,
    data_capability_service.STATE_NOT_CONFIGURED,
    data_capability_service.STATE_FAILED,
}
READY_PACKET_STATES = {"ready", "ok", "completed", "success", "available", "可用", "今日已刷新", "已刷新"}
CACHED_PACKET_STATES = {"cached", "partial", "stale", "using_cache", "使用缓存", "部分可用", "近期无数据"}
WAITING_PACKET_STATES = {
    "waiting",
    "missing",
    "requires_manual_refresh",
    "manual_required",
    "pending",
    "待刷新",
    "待验证",
    "需要手动刷新",
}
FAILED_PACKET_STATES = {
    "failed",
    "error",
    "failure",
    "permission_denied",
    "disabled_this_session",
    "network_failed",
    "not_configured",
    "权限不足",
    "本会话跳过",
    "失败",
}
PACKET_SECTION_ORDER = [
    ("dragon_tiger", "龙虎榜", "command_center_dragon_tiger_packet"),
    ("margin", "融资融券", "command_center_margin_packet"),
    ("moneyflow", "个股资金流", "command_center_moneyflow_packet"),
    ("limit_emotion", "涨跌停/情绪", "command_center_limit_emotion_packet"),
    ("chip_radar", "筹码/胜率", "command_center_chip_packet"),
]

FACT_RECOVERY_CONFIG = {
    key: {
        "label": label,
        "writes_packet": packet_key,
        "toolbox_entry": {
            "dragon_tiger": "高级工具箱 / 下一票雷达 / 龙虎榜",
            "margin": "高级工具箱 / 融资 ETF / 融资融券",
            "moneyflow": "高级工具箱 / A股专业实盘 / 个股资金流",
            "limit_emotion": "高级工具箱 / 数据源体检 / 涨跌停情绪",
            "chip_radar": "高级工具箱 / 量化推演 / 筹码胜率",
        }[key],
        "action_label": {
            "dragon_tiger": "强制刷新龙虎榜",
            "margin": "强制刷新融资融券",
            "moneyflow": "强制刷新个股资金流",
            "limit_emotion": "强制刷新涨跌停/情绪",
            "chip_radar": "强制刷新筹码/胜率",
        }[key],
    }
    for key, label, packet_key in PACKET_SECTION_ORDER
}

FACT_RECOVERY_LEGACY_TABS = {
    "dragon_tiger": "下一票雷达",
    "margin": "融资 ETF",
    "moneyflow": "今日关注池",
    "limit_emotion": "数据源体检",
    "chip_radar": "量化推演",
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def refresh_caption() -> str:
    return REFRESH_CAPTION


def empty_notice() -> str:
    return EMPTY_NOTICE


def _capability_items(capability_packet: Any = None) -> list[dict]:
    packet = as_mapping(capability_packet)
    items = packet.get("items") or []
    return [as_mapping(item) for item in items if as_mapping(item)]


def build_a_share_status_strip(professional_facts: Any = None, capability_packet: Any = None) -> dict:
    facts = as_mapping(professional_facts)
    capability = as_mapping(capability_packet or facts.get("data_capability"))
    items = _capability_items(capability)
    has_cache = has_a_share_professional_cache(facts)
    available = []
    restricted = []
    manual = []
    pending = []
    for item in items:
        state = item.get("capability_state")
        if state in AVAILABLE_STATES or item.get("ok"):
            available.append(item)
        elif state in RESTRICTED_STATES:
            restricted.append(item)
        elif state == data_capability_service.STATE_REQUIRES_MANUAL_REFRESH:
            manual.append(item)
        else:
            pending.append(item)
    if restricted:
        status_label = "部分接口受限"
        tone = "failed"
    elif has_cache and available:
        status_label = "已读取缓存"
        tone = "ready"
    elif has_cache:
        status_label = "使用缓存"
        tone = "stale"
    elif manual:
        status_label = "自动检测中"
        tone = "missing"
    else:
        status_label = "待检测"
        tone = "missing"
    if items:
        summary = (
            f"可用 {len(available)}｜受限/失败 {len(restricted)}｜"
            f"待验证 {len(pending)}｜自动检测中 {len(manual)}"
        )
    else:
        summary = "暂无 A股专业事实缓存；页面会按当前标的自动检测 Tushare。"
    return {
        "title": "A股专业数据能力",
        "status_label": status_label,
        "tone": tone,
        "summary": summary,
        "checked_at": to_text(capability.get("checked_at") or facts.get("updated_at")),
        "source": to_text(capability.get("source") or facts.get("data_source"), "Tushare A股专业事实"),
        "items": items,
        "manual_note": "专业事实按当前标的自动检测并受 TTL 保护；DeepSeek 未调用。",
        "deepseek_called": False,
    }


def build_a_share_status_completion_notice(status_strip: Any = None, task_label: str = "A股盘口与情绪状态整理") -> dict:
    """Separate UI step completion from whether the underlying data is usable."""
    strip = as_mapping(status_strip)
    status_label = _first_text(strip.get("status_label"), default="待检测")
    tone = _first_text(strip.get("tone"), default="missing")
    summary = _first_text(strip.get("summary"), default="暂无 A股专业事实缓存；页面会按当前标的自动检测 Tushare。")
    if tone == "failed" or "受限" in status_label or "失败" in status_label:
        prefix = "部分受限"
        state = "complete"
        decision_guardrail = "受限接口未恢复前，不能把缺失数据当成无风险，也不能支持加仓、追高或加融资。"
    elif tone == "stale" or "缓存" in status_label:
        prefix = "使用缓存"
        state = "complete"
        decision_guardrail = "缓存能防白屏，但执行前必须复核交易日、来源和更新时间。"
    elif "手动" in status_label or "自动检测" in status_label or status_label in {"待检测", "待刷新"}:
        prefix = "自动检测中"
        state = "complete"
        decision_guardrail = "自动检测未取得可用结果前，只展示安全空态或上次结果，不能把缺口当作利好。"
    else:
        prefix = "已整理"
        state = "complete"
        decision_guardrail = "数据状态已整理；交易动作仍需价格、纪律和仓位共同确认。"
    return {
        "label": f"{prefix}：{task_label}｜{summary}",
        "state": state,
        "prefix": prefix,
        "status_label": status_label,
        "tone": tone,
        "summary": summary,
        "decision_guardrail": decision_guardrail,
        "manual_note": "这里表示状态整理已结束，不代表所有 Tushare 专业接口均可用。",
        "deepseek_called": False,
    }


def _packet_state(packet: Mapping[str, Any]) -> str:
    raw_values = [
        packet.get("status"),
        packet.get("data_status"),
        packet.get("state"),
        packet.get("capability_state"),
    ]
    for value in raw_values:
        text = to_text(value).lower()
        if text in READY_PACKET_STATES:
            return "ready"
        if text in FAILED_PACKET_STATES:
            return "failed"
        if text in CACHED_PACKET_STATES:
            return "cached"
        if text in WAITING_PACKET_STATES:
            return "waiting"
    if packet.get("available") is True or packet.get("ok") is True:
        return "ready"
    if packet.get("manual_gate") or packet.get("requires_manual_refresh"):
        return "waiting"
    return "waiting" if not packet else "cached"


def _packet_state_label(state: str) -> str:
    return {
        "ready": "已回流",
        "cached": "使用缓存/待复核",
        "failed": "受限/失败",
        "waiting": "自动检测中",
    }.get(state, "待验证")


def _packet_tone(state: str) -> str:
    return {
        "ready": "ready",
        "cached": "stale",
        "failed": "failed",
        "waiting": "missing",
    }.get(state, "missing")


def _fact_recovery_action(key: str, state: str, packet: Mapping[str, Any]) -> dict:
    config = FACT_RECOVERY_CONFIG.get(key, {})
    label = _first_text(config.get("label"), key, default="A股事实")
    api = _first_text(packet.get("api"), default=SECTION_SPECS.get(key, ("", "", ""))[1])
    writes_packet = _first_text(config.get("writes_packet"), default=f"command_center_{key}_packet")
    legacy_tab = FACT_RECOVERY_LEGACY_TABS.get(key, "今日关注池")
    if state == "ready":
        action_label = "无需恢复"
        reason = f"{label}已回流；只需复核交易日、来源和口径。"
        refresh_policy = "not_needed"
    elif state == "failed":
        action_label = _first_text(config.get("action_label"), default=f"强制刷新{label}")
        reason = f"{label}受限/失败；不能把缺失写成利好，需检查权限、积分或网络。"
        refresh_policy = "button_gated"
    elif state == "cached":
        action_label = _first_text(config.get("action_label"), default=f"强制刷新{label}")
        reason = f"{label}正在使用缓存或待复核；执行前需要确认交易日和更新时间。"
        refresh_policy = "button_gated"
    else:
        action_label = _first_text(config.get("action_label"), default=f"强制刷新{label}")
        reason = f"{label}自动检测中或待验证；强制刷新可绕过 TTL。"
        refresh_policy = "button_gated"
    return {
        "key": key,
        "label": label,
        "state": state,
        "status_label": _packet_state_label(state),
        "action_label": action_label,
        "reason": reason,
        "toolbox_entry": _first_text(config.get("toolbox_entry"), default="高级工具箱 / 数据源体检"),
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "writes_packet": writes_packet,
        "api_hint": api,
        "refresh_policy": refresh_policy,
        "source_label": "旧版 A股事实卡",
        "deepseek_called": False,
    }


def _fact_packet_route_summary(label: str, writes_packet: str) -> str:
    return f"{label} → {writes_packet} → 综合推演中心数据能力状态 / A股事实回流 / 今日总决策依据链。"


def _fact_decision_chain_effect(
    label: str,
    state: str,
    packet: Mapping[str, Any],
    writes_packet: str,
) -> str:
    existing = _first_text(
        packet.get("decision_chain_effect"),
        packet.get("decision_guardrail"),
        packet.get("decision_impact"),
    )
    if existing:
        return existing
    if state == "ready":
        return f"{label}已回流 {writes_packet}，可进入综合中心证据链；仍需复核交易日、来源和仓位纪律。"
    if state == "cached":
        return f"{label}当前只作为缓存/待复核证据；执行前必须确认日期、来源和覆盖口径。"
    if state == "failed":
        return f"{label}受限/失败时，{writes_packet} 未恢复前不能支撑加仓、追高、加融资或把风险写成已排除。"
    return f"{label}尚未回流 {writes_packet}；综合中心只能把这项标记为待验证，不能当作已验证事实。"


def _packet_risk_text(packet: Mapping[str, Any]) -> str:
    notes = packet.get("risk_notes")
    if isinstance(notes, (list, tuple)):
        return _first_text(*notes)
    return _first_text(notes, packet.get("warning"), packet.get("error"), packet.get("manual_required_text"))


def _packet_summary_item(key: str, label: str, source_key: str, packet_value: Any = None) -> dict:
    packet = as_mapping(packet_value)
    state = _packet_state(packet)
    default_api = SECTION_SPECS.get(key, ("", "", ""))[1]
    recovery_action = _fact_recovery_action(key, state, packet)
    writes_packet = recovery_action.get("writes_packet") or f"command_center_{key}_packet"
    return {
        "key": key,
        "label": label,
        "packet": source_key,
        "state": state,
        "status": _packet_state_label(state),
        "tone": _packet_tone(state),
        "data_status": _first_text(packet.get("data_status"), default="missing" if state == "waiting" else state),
        "source": _first_text(packet.get("source"), default="Tushare A股专业事实缓存"),
        "api": _first_text(packet.get("api"), default=default_api),
        "updated_at": _first_text(packet.get("updated_at"), packet.get("trade_date"), packet.get("date")),
        "summary": _first_text(packet.get("summary"), packet.get("message"), default=SECTION_SPECS.get(key, ("", "", ""))[2]),
        "risk_note": _packet_risk_text(packet),
        "decision_chain_effect": _fact_decision_chain_effect(label, state, packet, writes_packet),
        "packet_route_summary": _fact_packet_route_summary(label, writes_packet),
        "recovery_action": recovery_action,
        "deepseek_called": bool(packet.get("deepseek_called", False)),
    }


def _to_number(value: Any) -> float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if not text or text in {"--", "暂无", "N/A", "None", "nan"}:
            return None
        try:
            return float(text)
        except Exception:
            return None
    return None


def _format_yi(value: Any) -> str:
    number = _to_number(value)
    return "暂无" if number is None else f"{number:.2f}亿"


def _format_flow_yi(value: Any) -> str:
    number = _to_number(value)
    return "暂无" if number is None else f"{number:+.2f}亿"


def _format_pct(value: Any) -> str:
    number = _to_number(value)
    return "暂无" if number is None else f"{number:+.2f}%"


def _format_plain_pct(value: Any) -> str:
    number = _to_number(value)
    return "暂无" if number is None else f"{number:.2f}%"


def _format_price(value: Any) -> str:
    number = _to_number(value)
    return "暂无" if number is None else f"¥{number:.2f}"


def _format_plain(value: Any) -> str:
    text = to_text(value)
    return text if text else "暂无"


def _format_source_caption(packet: Mapping[str, Any]) -> str:
    source = _first_text(packet.get("source"), default="Tushare A股专业事实缓存")
    api = _first_text(packet.get("api"))
    updated_at = _first_text(packet.get("updated_at"), default="未知")
    trade_date = _first_text(packet.get("trade_date"))
    pieces = [f"数据源：{source}" + (f" {api}" if api else ""), f"本地拉取时间：{updated_at}"]
    if trade_date:
        pieces.append(f"数据日期：{trade_date}")
    return "｜".join(pieces)


def _normalize_table_rows(value: Any, limit: int = 8) -> list[dict]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    for item in value:
        row = as_mapping(item)
        if row:
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _primary_fact_card(key: str, title: str, packet_value: Any, metrics: list[dict], captions: list[str]) -> dict:
    packet = as_mapping(packet_value)
    state = _packet_state(packet)
    summary = _first_text(packet.get("summary"), packet.get("message"), default=SECTION_SPECS.get(key, ("", "", ""))[2])
    recovery_action = _fact_recovery_action(key, state, packet)
    writes_packet = recovery_action.get("writes_packet") or f"command_center_{key}_packet"
    label = FACT_RECOVERY_CONFIG.get(key, {}).get("label") or title
    return {
        "key": key,
        "title": title,
        "state": state,
        "status": _packet_state_label(state),
        "tone": _packet_tone(state),
        "message": summary,
        "metrics": metrics if state == "ready" else [],
        "captions": [item for item in captions if item and item != "暂无"] if state == "ready" else [],
        "source_caption": _format_source_caption(packet),
        "risk_note": _packet_risk_text(packet),
        "decision_chain_effect": _fact_decision_chain_effect(label, state, packet, writes_packet),
        "packet_route_summary": _fact_packet_route_summary(label, writes_packet),
        "recovery_action": recovery_action,
        "deepseek_called": bool(packet.get("deepseek_called", False)),
    }


def _secondary_fact_section(
    key: str,
    title: str,
    packet_value: Any,
    metrics: list[dict],
    captions: list[str],
    tables: list[dict] | None = None,
) -> dict:
    packet = as_mapping(packet_value)
    state = _packet_state(packet)
    summary = _first_text(packet.get("summary"), packet.get("message"), default=SECTION_SPECS.get(key, ("", "", ""))[2])
    recovery_action = _fact_recovery_action(key, state, packet)
    writes_packet = recovery_action.get("writes_packet") or f"command_center_{key}_packet"
    label = FACT_RECOVERY_CONFIG.get(key, {}).get("label") or title
    return {
        "key": key,
        "title": title,
        "state": state,
        "status": _packet_state_label(state),
        "tone": _packet_tone(state),
        "message": summary,
        "metrics": metrics if state == "ready" else [],
        "captions": [item for item in captions if item and item != "暂无"] if state == "ready" else [],
        "tables": tables if state == "ready" else [],
        "source_caption": _format_source_caption(packet),
        "risk_note": _packet_risk_text(packet),
        "decision_chain_effect": _fact_decision_chain_effect(label, state, packet, writes_packet),
        "packet_route_summary": _fact_packet_route_summary(label, writes_packet),
        "recovery_action": recovery_action,
        "deepseek_called": bool(packet.get("deepseek_called", False)),
    }


def build_legacy_a_share_primary_fact_cards(
    *,
    dragon_tiger_packet: Any = None,
    margin_packet: Any = None,
    moneyflow_packet: Any = None,
) -> dict:
    dragon = as_mapping(dragon_tiger_packet)
    margin = as_mapping(margin_packet)
    moneyflow = as_mapping(moneyflow_packet)
    cards = [
        _primary_fact_card(
            "dragon_tiger",
            "🐯 龙虎榜追踪",
            dragon,
            [
                {"label": "上榜日期", "value": _format_plain(dragon.get("trade_date"))},
                {
                    "label": "收盘价 / 涨跌幅",
                    "value": f"{_format_price(dragon.get('close'))} / {_format_pct(dragon.get('pct_change'))}",
                },
                {
                    "label": "买入 / 卖出 / 净买入",
                    "value": (
                        f"{_format_yi(dragon.get('buy_amount_yi'))} / "
                        f"{_format_yi(dragon.get('sell_amount_yi'))} / "
                        f"{_format_flow_yi(dragon.get('net_buy_amount_yi'))}"
                    ),
                },
            ],
            [
                f"上榜原因：{dragon.get('reason')}" if to_text(dragon.get("reason")) else "",
                f"机构席位摘要：{dragon.get('inst_summary')}" if to_text(dragon.get("inst_summary")) else "",
                f"席位状态：{dragon.get('activity_state')}" if to_text(dragon.get("activity_state")) else "",
            ],
        ),
        _primary_fact_card(
            "margin",
            "💰 融资融券监测",
            margin,
            [
                {"label": "融资余额", "value": _format_yi(margin.get("financing_balance_yi"))},
                {"label": "融资买入额", "value": _format_yi(margin.get("financing_buy_yi"))},
                {
                    "label": "融资融券余额 / 融券余量",
                    "value": (
                        _format_yi(margin.get("margin_balance_yi"))
                        if _to_number(margin.get("margin_balance_yi")) is not None
                        else _format_plain(margin.get("short_sell_volume"))
                    ),
                },
            ],
            [f"杠杆状态：{margin.get('leverage_state')}" if to_text(margin.get("leverage_state")) else ""],
        ),
        _primary_fact_card(
            "moneyflow",
            "💧 个股资金流向",
            moneyflow,
            [
                {"label": "主力净流入", "value": _format_flow_yi(moneyflow.get("main_net_yi"))},
                {"label": "大单净流入", "value": _format_flow_yi(moneyflow.get("large_net_yi"))},
                {
                    "label": "中单 / 小单净流入",
                    "value": f"{_format_flow_yi(moneyflow.get('medium_net_yi'))} / {_format_flow_yi(moneyflow.get('small_net_yi'))}",
                },
                {"label": "近5日主力净流入合计", "value": _format_flow_yi(moneyflow.get("five_day_main_net_yi"))},
            ],
            [
                f"最近资金方向：{moneyflow.get('direction') or moneyflow.get('flow_state')}"
                if to_text(moneyflow.get("direction") or moneyflow.get("flow_state"))
                else "",
                f"资金结构评价：{moneyflow.get('summary')}" if to_text(moneyflow.get("summary")) else "",
            ],
        ),
    ]
    return {
        "title": "A股专业主事实",
        "cards": cards,
        "deepseek_called": False,
    }


def build_legacy_a_share_secondary_fact_sections(
    *,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
) -> dict:
    limit = as_mapping(limit_emotion_packet)
    chip = as_mapping(chip_packet)
    limit_records = _normalize_table_rows(limit.get("limit_records"), limit=5)
    concept_rows = _normalize_table_rows(limit.get("concept_top5"), limit=5)
    chip_areas = _normalize_table_rows(chip.get("chips_top_areas"), limit=5)
    sections = [
        _secondary_fact_section(
            "limit_emotion",
            "📈 A股情绪与涨跌停边界",
            limit,
            [
                {"label": "涨停价", "value": _format_price(limit.get("up_limit"))},
                {"label": "跌停价", "value": _format_price(limit.get("down_limit"))},
                {"label": "距涨停", "value": _format_pct(limit.get("distance_to_up_pct"))},
                {"label": "距跌停", "value": _format_pct(limit.get("distance_to_down_pct"))},
                {"label": "数据日期", "value": _format_plain(limit.get("trade_date"))},
            ],
            [
                f"情绪状态：{limit.get('emotion_state')}" if to_text(limit.get("emotion_state")) else "",
                "涨跌停/炸板记录只是事件证据，不单独构成买入理由。",
            ],
            [
                {
                    "title": "近5日涨跌停 / 炸板 / 连板记录",
                    "rows": limit_records,
                    "empty_message": "近5日未见该股涨跌停/炸板记录。",
                },
                {
                    "title": "当日涨停概念强度 Top 5",
                    "rows": concept_rows,
                    "empty_message": "暂未取得当日涨停概念强度数据。",
                },
            ],
        ),
        _secondary_fact_section(
            "chip_radar",
            "🧬 筹码/胜率雷达",
            chip,
            [
                {"label": "数据日期", "value": _format_plain(chip.get("trade_date"))},
                {"label": "获利盘比例 / 胜率", "value": _format_plain_pct(chip.get("winner_rate"))},
                {"label": "加权平均筹码成本", "value": _format_price(chip.get("weight_avg"))},
                {"label": "当前价相对筹码中枢", "value": _format_pct(chip.get("current_vs_weight_avg_pct"))},
            ],
            [
                (
                    "筹码成本 5% / 50% / 95% 分位："
                    f"{_format_price(chip.get('cost_5pct'))} / "
                    f"{_format_price(chip.get('cost_50pct'))} / "
                    f"{_format_price(chip.get('cost_95pct'))}"
                ),
                f"筹码压力评价：{chip.get('chip_pressure_comment') or chip.get('pressure_state')}"
                if to_text(chip.get("chip_pressure_comment") or chip.get("pressure_state"))
                else "",
                f"筹码结构评价：{chip.get('chip_structure_comment')}" if to_text(chip.get("chip_structure_comment")) else "",
                (
                    "筹码密集区："
                    + "；".join(
                        f"{_format_price(item.get('price'))} / {_format_plain_pct(item.get('percent'))}"
                        for item in chip_areas
                    )
                    if chip_areas
                    else ""
                ),
            ],
        ),
    ]
    return {
        "title": "A股情绪与筹码事实",
        "sections": sections,
        "deepseek_called": False,
    }


def build_legacy_a_share_war_room_inputs(
    *,
    chip_packet: Any = None,
    limit_emotion_packet: Any = None,
    moneyflow_packet: Any = None,
    technical_facts: Any = None,
    technical_snapshot: Any = None,
    position_profile: Any = None,
    position_status: str = "",
) -> dict:
    chip = as_mapping(chip_packet)
    limit = as_mapping(limit_emotion_packet)
    moneyflow = as_mapping(moneyflow_packet)
    technical = as_mapping(technical_facts)
    snapshot = as_mapping(technical_snapshot)
    profile = as_mapping(position_profile)
    ma20 = _to_number(technical.get("ma20") or technical.get("ma20_value"))
    if ma20 is None:
        ma20 = _to_number(snapshot.get("ma20"))
    normalized_position_state = _first_text(profile.get("normalized_position_state"), position_status)
    return {
        "chip_center": _to_number(chip.get("weight_avg")),
        "ma20": ma20,
        "ma60": _to_number(technical.get("ma60") or snapshot.get("ma60")),
        "limit_up": _to_number(limit.get("up_limit")),
        "limit_down": _to_number(limit.get("down_limit")),
        "today_main_net_yi": _to_number(moneyflow.get("main_net_yi")),
        "five_day_main_net_yi": _to_number(moneyflow.get("five_day_main_net_yi")),
        "position_profile": profile,
        "position_state": normalized_position_state,
        "is_holding": normalized_position_state == "已持仓",
        "cost_price": profile.get("cost_price") if profile.get("cost_price") else None,
        "shares": profile.get("holding_units") if profile.get("allow_pnl") else None,
        "source": "command_center_*_packet",
        "source_fields": {
            "chip_center": "command_center_chip_packet.weight_avg",
            "limit_up": "command_center_limit_emotion_packet.up_limit",
            "limit_down": "command_center_limit_emotion_packet.down_limit",
            "today_main_net_yi": "command_center_moneyflow_packet.main_net_yi",
            "five_day_main_net_yi": "command_center_moneyflow_packet.five_day_main_net_yi",
        },
        "deepseek_called": False,
    }


def _packet_ready(packet: Mapping[str, Any]) -> bool:
    return _packet_state(packet) == "ready"


def _packet_updated_at(packet: Mapping[str, Any]) -> str:
    return _first_text(packet.get("updated_at"), packet.get("trade_date"), packet.get("date"))


def _packet_message(packet: Mapping[str, Any]) -> str:
    return _first_text(packet.get("summary"), packet.get("message"), packet.get("manual_required_text"), default="暂无可验证数据")


def build_legacy_a_share_prompt_fact_payloads(
    *,
    dragon_tiger_packet: Any = None,
    margin_packet: Any = None,
    moneyflow_packet: Any = None,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
) -> dict:
    dragon = as_mapping(dragon_tiger_packet)
    margin = as_mapping(margin_packet)
    moneyflow = as_mapping(moneyflow_packet)
    limit = as_mapping(limit_emotion_packet)
    chip = as_mapping(chip_packet)
    dragon_ready = _packet_ready(dragon)
    margin_ready = _packet_ready(margin)
    moneyflow_ready = _packet_ready(moneyflow)
    limit_ready = _packet_ready(limit)
    chip_ready = _packet_ready(chip)
    limit_records = _normalize_table_rows(limit.get("limit_records"), limit=5)
    concept_rows = _normalize_table_rows(limit.get("concept_top5"), limit=5)
    boundary_available = bool(limit_ready and (limit.get("boundary_available") or limit.get("up_limit") or limit.get("down_limit")))
    records_available = bool(limit_ready and (limit.get("records_available") or limit_records))
    return {
        "dragon_tiger": {
            "available": dragon_ready,
            "latest_date": _first_text(dragon.get("trade_date")),
            "reason": dragon.get("reason") if dragon_ready else "",
            "net_buy_amount_yi": dragon.get("net_buy_amount_yi") if dragon_ready else "",
            "inst_summary": dragon.get("inst_summary") if dragon_ready else "",
            "message": "" if dragon_ready else _packet_message(dragon),
            "source": _first_text(dragon.get("source"), default="Tushare 龙虎榜缓存"),
            "api": _first_text(dragon.get("api"), default="top_list/top_inst"),
            "updated_at": _packet_updated_at(dragon),
        },
        "margin": {
            "available": margin_ready,
            "date": _first_text(margin.get("trade_date")),
            "financing_balance_yi": margin.get("financing_balance_yi") if margin_ready else "",
            "financing_buy_yi": margin.get("financing_buy_yi") if margin_ready else "",
            "margin_balance_yi": margin.get("margin_balance_yi") if margin_ready else "",
            "short_sell_volume": margin.get("short_sell_volume") if margin_ready else "",
            "message": "" if margin_ready else _packet_message(margin),
            "source": _first_text(margin.get("source"), default="Tushare margin_detail 缓存"),
            "api": _first_text(margin.get("api"), default="margin_detail"),
            "updated_at": _packet_updated_at(margin),
        },
        "moneyflow": {
            "available": moneyflow_ready,
            "date": _first_text(moneyflow.get("trade_date")),
            "main_net_yi": moneyflow.get("main_net_yi") if moneyflow_ready else "",
            "large_net_yi": moneyflow.get("large_net_yi") if moneyflow_ready else "",
            "medium_net_yi": moneyflow.get("medium_net_yi") if moneyflow_ready else "",
            "small_net_yi": moneyflow.get("small_net_yi") if moneyflow_ready else "",
            "five_day_main_net_yi": moneyflow.get("five_day_main_net_yi") if moneyflow_ready else "",
            "direction": _first_text(moneyflow.get("direction"), moneyflow.get("flow_state")) if moneyflow_ready else "",
            "structure": _first_text(moneyflow.get("summary"), moneyflow.get("flow_state")) if moneyflow_ready else "",
            "message": "" if moneyflow_ready else _packet_message(moneyflow),
            "source": _first_text(moneyflow.get("source"), default="Tushare moneyflow 缓存"),
            "api": _first_text(moneyflow.get("api"), default="moneyflow"),
            "updated_at": _packet_updated_at(moneyflow),
        },
        "limit_emotion": {
            "available": limit_ready,
            "boundary_available": boundary_available,
            "records_available": records_available,
            "latest_date": _first_text(limit.get("trade_date")),
            "concept_date": _first_text(limit.get("trade_date")),
            "up_limit": limit.get("up_limit") if boundary_available else "",
            "down_limit": limit.get("down_limit") if boundary_available else "",
            "distance_to_up_pct": limit.get("distance_to_up_pct") if boundary_available else "",
            "distance_to_down_pct": limit.get("distance_to_down_pct") if boundary_available else "",
            "limit_records": limit_records if records_available else [],
            "concept_top5": concept_rows if limit_ready else [],
            "message": "" if limit_ready else _packet_message(limit),
            "source": _first_text(limit.get("source"), default="Tushare 涨跌停/情绪缓存"),
            "api": _first_text(limit.get("api"), default="stk_limit / limit_list_d / limit_cpt_list"),
            "updated_at": _packet_updated_at(limit),
        },
        "chip_radar": {
            "available": chip_ready,
            "trade_date": _first_text(chip.get("trade_date")),
            "winner_rate": chip.get("winner_rate") if chip_ready else "",
            "weight_avg": chip.get("weight_avg") if chip_ready else "",
            "cost_5pct": chip.get("cost_5pct") if chip_ready else "",
            "cost_50pct": chip.get("cost_50pct") if chip_ready else "",
            "cost_95pct": chip.get("cost_95pct") if chip_ready else "",
            "current_vs_weight_avg_pct": chip.get("current_vs_weight_avg_pct") if chip_ready else "",
            "chip_band_width": chip.get("chip_band_width") if chip_ready else "",
            "chip_pressure_comment": _first_text(chip.get("chip_pressure_comment"), chip.get("pressure_state")) if chip_ready else "暂无可验证数据",
            "chip_structure_comment": chip.get("chip_structure_comment") if chip_ready else "暂无可验证数据",
            "chips_top_areas": _normalize_table_rows(chip.get("chips_top_areas"), limit=5) if chip_ready else [],
            "message": "" if chip_ready else _packet_message(chip),
            "source": _first_text(chip.get("source"), default="Tushare cyq_perf/cyq_chips 缓存"),
            "api": _first_text(chip.get("api"), default="cyq_perf/cyq_chips"),
            "updated_at": _packet_updated_at(chip),
        },
        "source": "command_center_*_packet",
        "deepseek_called": False,
    }


def build_legacy_a_share_packet_summary(
    *,
    dragon_tiger_packet: Any = None,
    margin_packet: Any = None,
    moneyflow_packet: Any = None,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
) -> dict:
    packets = {
        "dragon_tiger": dragon_tiger_packet,
        "margin": margin_packet,
        "moneyflow": moneyflow_packet,
        "limit_emotion": limit_emotion_packet,
        "chip_radar": chip_packet,
    }
    items = [
        _packet_summary_item(key, label, source_key, packets.get(key))
        for key, label, source_key in PACKET_SECTION_ORDER
    ]
    counts = {
        "ready": sum(1 for item in items if item["state"] == "ready"),
        "cached": sum(1 for item in items if item["state"] == "cached"),
        "waiting": sum(1 for item in items if item["state"] == "waiting"),
        "failed": sum(1 for item in items if item["state"] == "failed"),
    }
    if counts["failed"]:
        status_label = "部分接口受限"
        tone = "failed"
    elif counts["ready"] == len(items):
        status_label = "已全部回流"
        tone = "ready"
    elif counts["ready"] or counts["cached"]:
        status_label = "部分回流"
        tone = "stale" if counts["cached"] else "ready"
    else:
        status_label = "自动检测中"
        tone = "missing"
    return {
        "title": "A股专业事实回流",
        "status_label": status_label,
        "tone": tone,
        "summary": (
            f"已回流 {counts['ready']}｜使用缓存/待复核 {counts['cached']}｜"
            f"自动检测中 {counts['waiting']}｜受限/失败 {counts['failed']}"
        ),
        "counts": counts,
        "items": items,
        "manual_note": "以下结果区优先读取结构化状态；当前页按 TTL 自动检测当前标的 Tushare 分区，缺失项保留缓存/空态。",
        "deepseek_called": False,
    }


def has_a_share_professional_cache(professional_facts: Any = None) -> bool:
    payload = as_mapping(professional_facts)
    if payload.get("available"):
        return True
    for key in SECTION_SPECS:
        section = as_mapping(payload.get(key))
        if not section:
            continue
        if section.get("manual_gate"):
            continue
        if section.get("available") or section.get("updated_at") or section.get("latest_date") or section.get("date"):
            return True
    return False


def _manual_section(section_key: str, updated_at: str) -> dict:
    label, api, message = SECTION_SPECS[section_key]
    return {
        "available": False,
        "manual_gate": True,
        "requires_manual_refresh": True,
        "label": label,
        "source": "Tushare",
        "api": api,
        "updated_at": updated_at,
        "message": message,
        "warning": message,
        "deepseek_called": False,
    }


def build_manual_gate_a_share_professional_facts(stock_code: str = "", updated_at: str = "") -> dict:
    timestamp = to_text(updated_at)
    packet = {
        "available": False,
        "stock_code": to_text(stock_code),
        "data_source": "Tushare A股专业事实",
        "updated_at": timestamp,
        "missing_items": [
            "旧版 A股专业事实自动检测中；当前页会按 TTL 请求当前标的必要 Tushare 分区。",
        ],
        "manual_required_text": "等待自动检测完成；如需立即重跑，可使用强制刷新。",
        "deepseek_called": False,
    }
    for section_key in SECTION_SPECS:
        packet[section_key] = _manual_section(section_key, timestamp)
    packet["data_capability"] = data_capability_service.build_a_share_professional_capability_packet(
        packet,
        checked_at=timestamp,
    )
    return packet
