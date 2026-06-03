from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import market_data_capability as data_capability_service


SECTION_SPECS = {
    "dragon_tiger": ("龙虎榜", "top_list/top_inst", "龙虎榜待手动刷新；页面打开不会自动请求 Tushare top_list/top_inst。"),
    "margin": ("融资融券", "margin_detail", "融资融券待手动刷新；页面打开不会自动请求 Tushare margin_detail。"),
    "moneyflow": ("个股资金流", "moneyflow", "个股资金流待手动刷新；页面打开不会自动请求 Tushare moneyflow。"),
    "limit_emotion": (
        "涨跌停/情绪",
        "stk_limit / limit_list_d / limit_cpt_list",
        "涨跌停/情绪待手动刷新；页面打开不会自动请求 Tushare 涨跌停接口。",
    ),
    "chip_radar": ("筹码/胜率", "cyq_perf/cyq_chips", "筹码/胜率待手动刷新；页面打开不会自动请求 Tushare cyq_perf/cyq_chips。"),
}

REFRESH_CAPTION = "刷新会清除本页相关 Tushare 缓存；专业接口仍需点击对应检测/刷新按钮后才会请求，避免页面打开自动打重接口。"
EMPTY_NOTICE = "未检测到 A股专业事实缓存；为避免页面打开自动打重接口，当前只展示待刷新状态。请使用下方数据能力检测按钮。"

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
        status_label = "待手动刷新"
        tone = "missing"
    else:
        status_label = "待检测"
        tone = "missing"
    if items:
        summary = (
            f"可用 {len(available)}｜受限/失败 {len(restricted)}｜"
            f"待验证 {len(pending)}｜手动刷新 {len(manual)}"
        )
    else:
        summary = "暂无 A股专业事实缓存；页面打开不会自动请求 Tushare。"
    return {
        "title": "A股专业数据能力",
        "status_label": status_label,
        "tone": tone,
        "summary": summary,
        "checked_at": to_text(capability.get("checked_at") or facts.get("updated_at")),
        "source": to_text(capability.get("source") or facts.get("data_source"), "Tushare A股专业事实"),
        "items": items,
        "manual_note": "专业事实只读缓存或手动检测结果；DeepSeek 未调用。",
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
        "waiting": "待手动刷新",
    }.get(state, "待验证")


def _packet_tone(state: str) -> str:
    return {
        "ready": "ready",
        "cached": "stale",
        "failed": "failed",
        "waiting": "missing",
    }.get(state, "missing")


def _packet_risk_text(packet: Mapping[str, Any]) -> str:
    notes = packet.get("risk_notes")
    if isinstance(notes, (list, tuple)):
        return _first_text(*notes)
    return _first_text(notes, packet.get("warning"), packet.get("error"), packet.get("manual_required_text"))


def _packet_summary_item(key: str, label: str, source_key: str, packet_value: Any = None) -> dict:
    packet = as_mapping(packet_value)
    state = _packet_state(packet)
    default_api = SECTION_SPECS.get(key, ("", "", ""))[1]
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


def _primary_fact_card(key: str, title: str, packet_value: Any, metrics: list[dict], captions: list[str]) -> dict:
    packet = as_mapping(packet_value)
    state = _packet_state(packet)
    summary = _first_text(packet.get("summary"), packet.get("message"), default=SECTION_SPECS.get(key, ("", "", ""))[2])
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
        status_label = "待手动刷新"
        tone = "missing"
    return {
        "title": "A股专业事实回流",
        "status_label": status_label,
        "tone": tone,
        "summary": (
            f"已回流 {counts['ready']}｜使用缓存/待复核 {counts['cached']}｜"
            f"待手动刷新 {counts['waiting']}｜受限/失败 {counts['failed']}"
        ),
        "counts": counts,
        "items": items,
        "manual_note": "以下结果区优先读取 command_center_*_packet 规范状态；页面打开不会自动请求 Tushare，缺失项请手动检测/刷新。",
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
            "旧版 A股专业事实未手动刷新；页面打开只显示缓存/待刷新状态，不自动请求 Tushare。",
        ],
        "manual_required_text": "请通过 A股数据能力检测或对应刷新按钮手动请求；结果会回流到综合中心。",
        "deepseek_called": False,
    }
    for section_key in SECTION_SPECS:
        packet[section_key] = _manual_section(section_key, timestamp)
    packet["data_capability"] = data_capability_service.build_a_share_professional_capability_packet(
        packet,
        checked_at=timestamp,
    )
    return packet
