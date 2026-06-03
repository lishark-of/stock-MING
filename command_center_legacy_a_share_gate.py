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


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


def refresh_caption() -> str:
    return REFRESH_CAPTION


def empty_notice() -> str:
    return EMPTY_NOTICE


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
