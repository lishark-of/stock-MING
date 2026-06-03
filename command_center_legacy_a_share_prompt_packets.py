from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def build_empty_verified_technical_fact_packet() -> dict:
    return {
        "available": False,
        "facts": {},
        "missing_items": ["verified_technical_facts"],
        "updated_at": "",
    }


def _timestamp(updated_at: str = "") -> str:
    return updated_at or datetime.datetime.now().isoformat(timespec="seconds")


def build_next_day_plan_fact_packet(
    stock_code: str = "",
    stock_name: str = "",
    current_price: Any = None,
    position_profile: Any = None,
    trade_instruction: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    moneyflow_data: Any = None,
    limit_emotion_data: Any = None,
    chip_radar_data: Any = None,
    tushare_verified_source: Any = None,
    market_style_fact_packet: Any = None,
    verified_technical_facts: Any = None,
    updated_at: str = "",
) -> dict:
    position_profile = as_mapping(position_profile)
    trade_instruction = as_mapping(trade_instruction)
    dragon_data = as_mapping(dragon_data)
    margin_data = as_mapping(margin_data)
    moneyflow_data = as_mapping(moneyflow_data)
    limit_emotion_data = as_mapping(limit_emotion_data)
    chip_radar_data = as_mapping(chip_radar_data)
    tushare_verified_source = as_mapping(tushare_verified_source)
    market_style_fact_packet = as_mapping(market_style_fact_packet)
    verified_technical_facts = as_mapping(verified_technical_facts) or build_empty_verified_technical_fact_packet()

    moneyflow_available = bool(moneyflow_data.get("available"))
    dragon_available = bool(dragon_data.get("available"))
    margin_available = bool(margin_data.get("available"))
    limit_available = bool(limit_emotion_data.get("available"))
    limit_records_available = bool(limit_emotion_data.get("records_available"))
    boundary_available = bool(limit_emotion_data.get("boundary_available"))
    chip_available = bool(chip_radar_data.get("available"))
    api_results = as_mapping(tushare_verified_source.get("api_results"))

    missing_items = []
    if not moneyflow_available:
        missing_items.append("Tushare moneyflow")
    if not dragon_available:
        missing_items.append("Tushare top_list/top_inst")
    if not margin_available:
        missing_items.append("Tushare margin_detail")
    if not boundary_available:
        missing_items.append("Tushare stk_limit")
    if not limit_records_available:
        missing_items.append("Tushare limit_list_d")
    if not chip_available:
        missing_items.append("Tushare cyq_perf/cyq_chips")
    if not as_mapping(api_results.get("daily")).get("ok"):
        missing_items.append("Tushare daily")
    if not as_mapping(api_results.get("daily_basic")).get("ok"):
        missing_items.append("Tushare daily_basic")

    updated_sources = [
        moneyflow_data.get("updated_at"),
        dragon_data.get("updated_at"),
        margin_data.get("updated_at"),
        limit_emotion_data.get("updated_at"),
        chip_radar_data.get("updated_at"),
        tushare_verified_source.get("updated_at"),
    ]
    updated_sources = [item for item in updated_sources if item]

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "current_price": current_price if current_price is not None else "暂无可验证数据",
        "position_profile": {
            "position_status": position_profile.get("position_status") or "暂无可验证数据",
            "normalized_position_state": position_profile.get("normalized_position_state") or "暂无可验证数据",
            "position_confidence": position_profile.get("position_confidence") or "暂无可验证数据",
            "position_warning": position_profile.get("position_warning") or "",
            "allow_pnl": bool(position_profile.get("allow_pnl")),
            "allow_t_plan": bool(position_profile.get("allow_t_plan")),
            "allow_reduce_plan": bool(position_profile.get("allow_reduce_plan")),
            "allow_trial_entry": bool(position_profile.get("allow_trial_entry")),
            "capital_plan": position_profile.get("capital_plan") if position_profile.get("capital_plan") is not None else "暂无可验证数据",
            "cost_price": position_profile.get("cost_price") if position_profile.get("cost_price") is not None else "暂无可验证数据",
            "holding_units": position_profile.get("holding_units") if position_profile.get("holding_units") is not None else "暂无可验证数据",
            "position_summary": position_profile.get("profit_state") or "暂无可验证数据",
        },
        "price_boundary": {
            "available": boundary_available,
            "limit_up_price": limit_emotion_data.get("up_limit") if boundary_available else "暂无可验证数据",
            "limit_down_price": limit_emotion_data.get("down_limit") if boundary_available else "暂无可验证数据",
            "distance_to_limit_up": limit_emotion_data.get("distance_to_up_pct") if boundary_available else "暂无可验证数据",
            "distance_to_limit_down": limit_emotion_data.get("distance_to_down_pct") if boundary_available else "暂无可验证数据",
            "latest_date": limit_emotion_data.get("latest_date") if boundary_available else "",
            "note": "涨停价/跌停价仅作为交易边界参考，不是长期支撑压力",
        },
        "moneyflow": {
            "available": moneyflow_available,
            "latest_date": moneyflow_data.get("date") if moneyflow_available else "",
            "main_net_inflow_yi": moneyflow_data.get("main_net_yi") if moneyflow_available else "",
            "large_net_inflow_yi": moneyflow_data.get("large_net_yi") if moneyflow_available else "",
            "medium_net_inflow_yi": moneyflow_data.get("medium_net_yi") if moneyflow_available else "",
            "small_net_inflow_yi": moneyflow_data.get("small_net_yi") if moneyflow_available else "",
            "five_day_main_net_inflow_yi": moneyflow_data.get("five_day_main_net_yi") if moneyflow_available else "",
            "direction": moneyflow_data.get("direction") if moneyflow_available else "",
            "structure_comment": moneyflow_data.get("structure") if moneyflow_available else "",
            "note": "" if moneyflow_available else "暂无可验证数据",
        },
        "dragon_tiger": {
            "available": dragon_available,
            "trade_date": dragon_data.get("latest_date") if dragon_available else "",
            "reason": dragon_data.get("reason") if dragon_available else "",
            "net_buy_amount": dragon_data.get("net_buy_amount_yi") if dragon_available else "",
            "institution_summary": dragon_data.get("inst_summary") if dragon_available else "",
            "note": "" if dragon_available else "暂无可验证数据",
        },
        "margin": {
            "available": margin_available,
            "trade_date": margin_data.get("date") if margin_available else "",
            "financing_balance_yi": margin_data.get("financing_balance_yi") if margin_available else "",
            "financing_buy_yi": margin_data.get("financing_buy_yi") if margin_available else "",
            "margin_balance_yi": margin_data.get("margin_balance_yi") if margin_available else "",
            "short_sell_volume": margin_data.get("short_sell_volume") if margin_available else "",
            "note": "" if margin_available else "暂无可验证数据",
        },
        "limit_emotion": {
            "available": limit_available,
            "records_available": limit_records_available,
            "recent_limit_records": as_list(limit_emotion_data.get("limit_records")) if limit_records_available else [],
            "concept_top5": as_list(limit_emotion_data.get("concept_top5")) if limit_available else [],
            "note": "" if limit_records_available else "暂无可验证数据",
        },
        "chip_radar": {
            "available": chip_available,
            "trade_date": chip_radar_data.get("trade_date") if chip_available else "",
            "winner_rate": chip_radar_data.get("winner_rate") if chip_available else "",
            "weight_avg": chip_radar_data.get("weight_avg") if chip_available else "",
            "cost_5pct": chip_radar_data.get("cost_5pct") if chip_available else "",
            "cost_50pct": chip_radar_data.get("cost_50pct") if chip_available else "",
            "cost_95pct": chip_radar_data.get("cost_95pct") if chip_available else "",
            "current_vs_weight_avg_pct": chip_radar_data.get("current_vs_weight_avg_pct") if chip_available else "",
            "chip_band_width": chip_radar_data.get("chip_band_width") if chip_available else "",
            "chip_pressure_comment": chip_radar_data.get("chip_pressure_comment") if chip_available else "暂无可验证数据",
            "chip_structure_comment": chip_radar_data.get("chip_structure_comment") if chip_available else "暂无可验证数据",
            "chips_top_areas": as_list(chip_radar_data.get("chips_top_areas")) if chip_available else [],
            "note": "" if chip_available else "暂无可验证数据",
        },
        "daily": as_mapping(api_results.get("daily")) or {"ok": False, "rows": [], "error": "暂无可验证数据"},
        "daily_basic": as_mapping(api_results.get("daily_basic")) or {"ok": False, "rows": [], "error": "暂无可验证数据"},
        "verified_technical_facts": verified_technical_facts,
        "market_style": {
            "trade_date": market_style_fact_packet.get("trade_date", ""),
            "market_state": market_style_fact_packet.get("market_state") or "暂无可验证数据",
            "risk_switch": market_style_fact_packet.get("risk_switch") or "暂无可验证数据",
            "limit_up_count": market_style_fact_packet.get("limit_up_count", "暂无可验证数据"),
            "limit_down_count": market_style_fact_packet.get("limit_down_count", "暂无可验证数据"),
            "break_limit_count": market_style_fact_packet.get("break_limit_count", "暂无可验证数据"),
            "break_limit_rate": market_style_fact_packet.get("break_limit_rate", "暂无可验证数据"),
            "max_consecutive_limit": market_style_fact_packet.get("max_consecutive_limit", "暂无可验证数据"),
        },
        "trade_instruction": trade_instruction.get("one_line") or trade_instruction.get("action") or "暂无可验证数据",
        "data_missing_items": missing_items,
        "updated_at": max(updated_sources) if updated_sources else _timestamp(updated_at),
        "deepseek_called": False,
    }


def build_single_stock_war_room_fact_packet(
    stock_code: str = "",
    stock_name: str = "",
    current_price: Any = None,
    position_profile: Any = None,
    trade_instruction: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    moneyflow_data: Any = None,
    limit_emotion_data: Any = None,
    chip_radar_data: Any = None,
    tushare_verified_source: Any = None,
    market_style_fact_packet: Any = None,
    verified_technical_facts: Any = None,
    watch_targets: Any = None,
    ts_code: str = "",
    updated_at: str = "",
) -> dict:
    base_fact_packet = build_next_day_plan_fact_packet(
        stock_code,
        stock_name,
        current_price,
        position_profile,
        trade_instruction,
        dragon_data,
        margin_data,
        moneyflow_data,
        limit_emotion_data,
        chip_radar_data=chip_radar_data,
        tushare_verified_source=tushare_verified_source,
        market_style_fact_packet=market_style_fact_packet,
        verified_technical_facts=verified_technical_facts,
        updated_at=updated_at,
    )
    profile = as_mapping(base_fact_packet.get("position_profile"))
    watch_targets = as_list(watch_targets)
    tushare_verified_source = as_mapping(tushare_verified_source)

    return {
        "stock": {
            "ts_code": ts_code,
            "name": stock_name or "",
            "current_price": base_fact_packet.get("current_price", ""),
        },
        "position_profile": profile,
        "trade_instruction": base_fact_packet.get("trade_instruction", ""),
        "verified_technical_facts": base_fact_packet.get("verified_technical_facts", {}),
        "moneyflow": base_fact_packet.get("moneyflow", {}),
        "dragon_tiger": base_fact_packet.get("dragon_tiger", {}),
        "margin": base_fact_packet.get("margin", {}),
        "limit_emotion": base_fact_packet.get("limit_emotion", {}),
        "chip_radar": base_fact_packet.get("chip_radar", {}),
        "market_style": base_fact_packet.get("market_style", {}),
        "position_permissions": {
            "allow_t_plan": bool(profile.get("allow_t_plan")),
            "allow_reduce_plan": bool(profile.get("allow_reduce_plan")),
            "allow_trial_entry": bool(profile.get("allow_trial_entry")),
            "normalized_position_state": profile.get("normalized_position_state") or "",
        },
        "trend_validation_inputs": {
            "technical": base_fact_packet.get("verified_technical_facts", {}),
            "moneyflow": base_fact_packet.get("moneyflow", {}),
            "limit_emotion": base_fact_packet.get("limit_emotion", {}),
            "chip_radar": base_fact_packet.get("chip_radar", {}),
            "market_style": base_fact_packet.get("market_style", {}),
        },
        "rotation_context": {
            "watch_targets": watch_targets,
            "note": "第一版仅使用 session_state 或今日关注池线索，未做持久化",
        },
        "rules": {
            "no_auto_order": True,
            "position_unit": "成",
            "max_new_trial_position": "0.5–1成",
            "no_full_position": True,
        },
        "tushare_verified_source": {
            "ok": bool(tushare_verified_source.get("ok")),
            "api_name": tushare_verified_source.get("api_name", ""),
            "updated_at": tushare_verified_source.get("updated_at", ""),
            "status": tushare_verified_source.get("status", ""),
        },
        "data_missing_items": base_fact_packet.get("data_missing_items", []),
        "updated_at": base_fact_packet.get("updated_at", ""),
        "deepseek_called": False,
    }
