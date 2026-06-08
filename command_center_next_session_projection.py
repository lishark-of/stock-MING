from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import statistics
from collections.abc import Mapping
from numbers import Number
from typing import Any


SCHEMA_VERSION = "next_session_operation_projection.v1"
PACKET_KEY = "command_center_next_session_projection_packet"
REQUIRED_FACT_KEYS = (
    ("moneyflow", "资金流"),
    ("dragon_tiger", "龙虎榜"),
    ("margin", "融资融券"),
    ("hard_risk", "公告/硬风险"),
    ("limit_emotion", "涨跌停/情绪"),
    ("chip_radar", "筹码/胜率"),
    ("volume_amount", "成交额/成交量"),
)
FACT_DEFAULT_INTERFACES = {
    "moneyflow": ["tushare.moneyflow"],
    "dragon_tiger": ["tushare.top_list", "tushare.top_inst"],
    "margin": ["tushare.margin_detail"],
    "hard_risk": [
        "tushare.anns_d",
        "tushare.forecast",
        "tushare.stk_holdertrade",
        "tushare.share_float",
        "tushare.pledge_stat",
        "tushare.pledge_detail",
        "tushare.stk_surv",
    ],
    "limit_emotion": ["tushare.stk_limit", "tushare.limit_list_d", "tushare.limit_cpt_list"],
    "chip_radar": ["tushare.cyq_perf", "tushare.cyq_chips"],
    "volume_amount": ["tushare.daily", "tushare.daily_basic"],
}
TRUTHY_STATUSES = {"verified", "ready", "completed", "available"}
BLOCKING_STATUSES = {"blocked", "missing", "stale", "pending", "failed", "timeout"}
FACT_CALL_STATUS_TO_LINEAGE_STATUS = {
    "verified_present": "verified",
    "verified_no_record": "verified",
    "called_success": "verified",
    "empty_window": "pending",
    "not_called": "pending",
    "permission_denied": "blocked",
    "parameter_error": "blocked",
    "parse_error": "blocked",
    "missing_packet": "missing",
    "stale_cache": "stale",
}
FACT_CALL_STATUS_LABELS = {
    "verified_present": "真实返回",
    "verified_no_record": "成功无记录",
    "called_success": "调用成功",
    "empty_window": "窗口无覆盖",
    "not_called": "未调用",
    "permission_denied": "权限不足",
    "parameter_error": "参数错误",
    "parse_error": "解析失败",
    "missing_packet": "packet 缺失",
    "stale_cache": "缓存过期",
}
UI_REQUIRED_LABELS = (
    "次日操作图谱",
    "真实日线",
    "量化推演",
    "交易纪律",
    "DeepSeek 整理",
    "非确定性预测",
)
FORBIDDEN_UI_LABELS = ("AI预测明日走势", "精准预测", "必然上涨", "真实未来曲线")
DEEPSEEK_MERGE_ALLOWED_KEYS = {"summary", "scenario_paths", "operation_zones", "annotations", "warnings"}
DEEPSEEK_MERGE_IMMUTABLE_KEYS = {
    "ts_code",
    "trade_date",
    "position_context",
    "shares",
    "cost_price",
    "current_price",
    "daily_close",
    "historical_series",
    "latest_close",
    "row_count",
    "source_interface",
    "a_share_fact_lineage_summary",
    "strategy_execution_packet",
    "quant_context",
    "data_lineage",
    "chart_render_model",
}
DEEPSEEK_REQUIRED_STRUCTURED_KEYS = {"scenario_paths", "operation_zones"}


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _to_number(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, Number):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "").replace("¥", "").replace("￥", "")
    if not text or text in {"暂无", "N/A", "None", "nan", "--"}:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    text = _to_text(now)
    return text or _dt.datetime.now().isoformat(timespec="seconds")


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _display_a_share_ticker(value: Any) -> str:
    text = _to_text(value).upper()
    if text.endswith(".SS"):
        return f"{text[:-3]}.SH"
    if text.isdigit() and len(text) == 6:
        if text.startswith("6"):
            return f"{text}.SH"
        if text.startswith(("0", "2", "3")):
            return f"{text}.SZ"
    return text


def _date_text(value: Any) -> str:
    text = _to_text(value)
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10] if len(text) >= 10 else text


def _safe_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_daily_rows(rows: Any, limit: int = 60) -> list[dict]:
    cleaned = []
    for raw in _as_list(rows):
        item = _as_mapping(raw)
        close = _to_number(item.get("close") or item.get("value") or item.get("price"))
        if close is None or close <= 0:
            continue
        date = _date_text(item.get("trade_date") or item.get("date") or item.get("asof") or item.get("x"))
        cleaned.append(
            {
                "trade_date": date,
                "close": round(close, 4),
                "open": _to_number(item.get("open")),
                "high": _to_number(item.get("high")),
                "low": _to_number(item.get("low")),
                "vol": _to_number(item.get("vol") or item.get("volume")),
                "amount": _to_number(item.get("amount")),
                "source": _to_text(item.get("source"), "tushare.daily"),
            }
        )
    cleaned.sort(key=lambda item: item.get("trade_date") or "")
    return cleaned[-limit:]


def _daily_rows_from_sources(
    *,
    daily_close_packet: Any = None,
    home_snapshot: Any = None,
    live_packet: Any = None,
) -> tuple[list[dict], dict]:
    packet = _as_mapping(daily_close_packet)
    snapshot = _as_mapping(home_snapshot)
    live = _as_mapping(live_packet)
    candidates = [
        packet,
        _as_mapping(snapshot.get("command_center_daily_close_packet")),
        _as_mapping(live.get("daily_close_packet")),
        _as_mapping(_as_mapping(live.get("market")).get("daily_close_packet")),
    ]
    for source_packet in candidates:
        rows = _clean_daily_rows(
            source_packet.get("rows")
            or source_packet.get("historical_series")
            or source_packet.get("historical_close_points")
            or source_packet.get("data")
        )
        if len(rows) >= 2 and source_packet.get("is_real_market_series", True):
            return rows, source_packet

    point_sources = [
        snapshot.get("historical_close_points"),
        snapshot.get("price_history_close"),
        live.get("historical_close_points"),
        _as_mapping(live.get("market")).get("historical_close_points"),
    ]
    for points in point_sources:
        rows = _clean_daily_rows(points)
        if len(rows) >= 2:
            return rows, {
                "source_interface": "tushare.daily",
                "source_packet": "historical_close_points",
                "updated_at": _to_text(snapshot.get("historical_close_updated_at") or live.get("historical_close_updated_at")),
                "is_real_market_series": True,
            }
    return [], packet


def _daily_lineage(rows: list[dict], source_packet: Mapping[str, Any], now: Any = None) -> dict:
    if not rows:
        return {
            "source_interface": "tushare.daily",
            "row_count": 0,
            "start_date": None,
            "end_date": None,
            "latest_close": None,
            "local_fetched_at": _to_text(source_packet.get("local_fetched_at") or source_packet.get("updated_at")) or None,
            "is_real_market_series": False,
            "status": "missing",
            "note": "真实日线缺失，无法生成真实历史段。",
        }
    return {
        "source_interface": _to_text(source_packet.get("source_interface"), "tushare.daily"),
        "row_count": len(rows),
        "start_date": rows[0].get("trade_date") or None,
        "end_date": rows[-1].get("trade_date") or None,
        "latest_close": rows[-1].get("close"),
        "local_fetched_at": _to_text(source_packet.get("local_fetched_at") or source_packet.get("updated_at"), _now_iso(now)),
        "is_real_market_series": True,
        "status": _to_text(source_packet.get("status"), "ready"),
        "source_packet": _to_text(source_packet.get("source_packet"), "command_center_daily_close_packet"),
    }


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 4)


def _volatility(values: list[float], window: int = 20) -> float | None:
    if len(values) < window + 1:
        return None
    returns = []
    for previous, current in zip(values[-window - 1:-1], values[-window:]):
        if previous:
            returns.append((current / previous) - 1)
    if len(returns) < 2:
        return None
    return round(statistics.stdev(returns) * 100, 4)


def _atr(rows: list[dict], window: int = 14) -> float | None:
    if len(rows) < 2:
        return None
    true_ranges = []
    for previous, current in zip(rows[:-1], rows[1:]):
        high = _to_number(current.get("high"))
        low = _to_number(current.get("low"))
        prev_close = _to_number(previous.get("close"))
        if high is None or low is None or prev_close is None:
            continue
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if not true_ranges:
        return None
    return round(sum(true_ranges[-window:]) / min(len(true_ranges), window), 4)


def _technical_context(rows: list[dict], lineage_items: list[dict]) -> dict:
    closes = [_to_number(item.get("close")) for item in rows]
    closes = [value for value in closes if value is not None]
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    latest = closes[-1] if closes else None
    support = []
    resistance = []
    if closes:
        support.append(round(min(closes[-20:]), 4))
        resistance.append(round(max(closes[-20:]), 4))
        if ma20:
            support.append(ma20)
    trend_state = "unknown"
    if latest is not None and ma5 is not None and ma20 is not None:
        if latest >= ma20 and ma5 >= ma20:
            trend_state = "uptrend"
        elif latest <= ma20 and ma5 <= ma20:
            trend_state = "downtrend"
        else:
            trend_state = "range"
    volume_item = next((item for item in lineage_items if item.get("fact_key") == "volume_amount"), {})
    return {
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "atr": _atr(rows),
        "volatility_20d": _volatility(closes),
        "support_levels": sorted(set(value for value in support if value is not None)),
        "resistance_levels": sorted(set(value for value in resistance if value is not None)),
        "volume_amount_status": _to_text(volume_item.get("status"), "pending"),
        "trend_state": trend_state,
    }


def _lineage_status_from_call_status(call_status: Any, fallback: str = "pending") -> str:
    status = _to_text(call_status)
    return FACT_CALL_STATUS_TO_LINEAGE_STATUS.get(status, fallback)


def _fact_call_ledger_items(ledger: Any = None, daily_close_packet: Any = None) -> list[dict]:
    payload = _as_mapping(ledger)
    items = [
        dict(item)
        for item in _as_list(payload.get("items") or payload.get("facts"))
        if isinstance(item, Mapping)
    ]
    by_key = {_to_text(item.get("fact_key")): item for item in items}
    daily = _as_mapping(daily_close_packet)
    if daily and "volume_amount" not in by_key:
        row_count = int(_to_number(daily.get("row_count"), 0) or 0)
        status = "verified_present" if daily.get("is_real_market_series") and row_count else "missing_packet"
        by_key["volume_amount"] = {
            "fact_key": "volume_amount",
            "fact_name": "成交额/成交量",
            "scope": "target_stock",
            "target_ts_code": daily.get("ts_code"),
            "symbol_filter_applied": True,
            "target_match_count": row_count,
            "market_row_count": row_count,
            "source_interfaces": ["tushare.daily", "tushare.daily_basic"],
            "source_packet": _to_text(daily.get("source_packet"), "command_center_daily_close_packet"),
            "request_params": daily.get("request_params") or {},
            "call_status": status,
            "row_count": row_count,
            "data_date": daily.get("latest_trade_date") or daily.get("end_date") or daily.get("trade_date"),
            "local_fetched_at": daily.get("local_fetched_at") or daily.get("updated_at"),
            "error_type": None,
            "error_message_safe": None,
            "lineage_status": _lineage_status_from_call_status(status),
            "is_market_absence_meaningful": False,
            "is_target_stock_evidence": status == "verified_present",
            "is_market_context_evidence": False,
            "scope_note": "目标股真实日线成交量/成交额。",
            "scope_breakdown": [
                {
                    "scope": "target_stock",
                    "call_status": status,
                    "row_count": row_count,
                    "target_match_count": row_count,
                    "is_target_stock_evidence": status == "verified_present",
                }
            ],
        }
    normalized = []
    for key, name in REQUIRED_FACT_KEYS:
        item = dict(by_key.get(key) or {})
        generated_default = key not in by_key
        call_status = _to_text(item.get("call_status"), "not_called")
        lineage_status = _to_text(item.get("lineage_status")) or _lineage_status_from_call_status(call_status)
        normalized.append(
            {
                "fact_key": key,
                "fact_name": _to_text(item.get("fact_name"), name),
                "scope": _to_text(item.get("scope"), "target_stock"),
                "target_ts_code": item.get("target_ts_code"),
                "symbol_filter_applied": bool(item.get("symbol_filter_applied")),
                "target_match_count": int(_to_number(item.get("target_match_count"), 0) or 0),
                "market_row_count": int(_to_number(_first(item.get("market_row_count"), item.get("row_count")), 0) or 0),
                "source_interfaces": list(item.get("source_interfaces") or FACT_DEFAULT_INTERFACES.get(key) or []),
                "source_packet": _to_text(item.get("source_packet"), f"command_center_{key}_packet"),
                "request_params": item.get("request_params") or {},
                "call_status": call_status,
                "call_status_label": FACT_CALL_STATUS_LABELS.get(call_status, "待验证"),
                "row_count": int(_to_number(item.get("row_count"), 0) or 0),
                "data_date": item.get("data_date") or None,
                "local_fetched_at": item.get("local_fetched_at") or None,
                "error_type": item.get("error_type") or None,
                "error_message_safe": item.get("error_message_safe") or None,
                "lineage_status": lineage_status,
                "is_market_absence_meaningful": bool(item.get("is_market_absence_meaningful")),
                "is_target_stock_evidence": bool(item.get("is_target_stock_evidence")),
                "is_market_context_evidence": bool(item.get("is_market_context_evidence")),
                "is_industry_or_concept_evidence": bool(item.get("is_industry_or_concept_evidence")),
                "scope_note": _to_text(item.get("scope_note")),
                "scope_breakdown": item.get("scope_breakdown") or [],
                "sections": item.get("sections") or [],
                "_generated_default": generated_default,
            }
        )
    return normalized


def _lineage_items(summary: Any, call_ledger_items: Any = None) -> list[dict]:
    payload = _as_mapping(summary)
    call_by_key = {
        _to_text(item.get("fact_key")): dict(item)
        for item in _as_list(call_ledger_items)
        if isinstance(item, Mapping)
    }
    by_key = {
        _to_text(item.get("fact_key")): dict(item)
        for item in _as_list(payload.get("items"))
        if isinstance(item, Mapping)
    }
    items = []
    for key, name in REQUIRED_FACT_KEYS:
        item = by_key.get(key) or {
            "fact_key": key,
            "fact_name": name,
            "status": "missing",
            "data_date": None,
            "local_fetched_at": None,
            "source_interfaces": [],
            "source_packet": "",
            "enters_projection": True,
            "enters_deepseek_prompt": True,
            "enters_core_action": False,
            "usage_note": "未取得可靠事实，不能当作已验证依据。",
        }
        call_item = call_by_key.get(key) or {}
        if call_item:
            item.update(
                {
                    "call_status": call_item.get("call_status"),
                    "call_status_label": call_item.get("call_status_label"),
                    "row_count": call_item.get("row_count"),
                    "scope": call_item.get("scope"),
                    "target_ts_code": call_item.get("target_ts_code"),
                    "symbol_filter_applied": call_item.get("symbol_filter_applied"),
                    "target_match_count": call_item.get("target_match_count"),
                    "market_row_count": call_item.get("market_row_count"),
                    "request_params": call_item.get("request_params"),
                    "error_type": call_item.get("error_type"),
                    "error_message_safe": call_item.get("error_message_safe"),
                    "is_market_absence_meaningful": call_item.get("is_market_absence_meaningful"),
                    "is_target_stock_evidence": call_item.get("is_target_stock_evidence"),
                    "is_market_context_evidence": call_item.get("is_market_context_evidence"),
                    "is_industry_or_concept_evidence": call_item.get("is_industry_or_concept_evidence"),
                    "scope_note": call_item.get("scope_note"),
                    "scope_breakdown": call_item.get("scope_breakdown") or [],
                    "sections": call_item.get("sections") or [],
                }
            )
            for field in ("data_date", "local_fetched_at", "source_packet", "source_interfaces"):
                if call_item.get(field) not in (None, "", [], {}):
                    item[field] = call_item.get(field)
            if not call_item.get("_generated_default") or key not in by_key:
                item["status"] = _to_text(call_item.get("lineage_status")) or _lineage_status_from_call_status(call_item.get("call_status"))
        status = _to_text(item.get("status"), "pending")
        if status not in TRUTHY_STATUSES and status not in BLOCKING_STATUSES and status != "cached":
            status = "pending"
        item["status"] = status
        item["fact_key"] = key
        item["fact_name"] = _to_text(item.get("fact_name"), name)
        item.setdefault("enters_projection", True)
        item.setdefault("enters_deepseek_prompt", True)
        item.setdefault("enters_core_action", False)
        items.append(item)
    return items


def _position_context(
    *,
    target: Any = "",
    name: Any = "",
    position_profile: Any = None,
    home_snapshot: Any = None,
    latest_close: float | None = None,
) -> dict:
    profile = _as_mapping(position_profile)
    snapshot = _as_mapping(home_snapshot)
    holding = _as_mapping(snapshot.get("holding_action"))
    source_fields = []

    def add_source(field: str, source: str, raw: Any, normalized: Any = None):
        if raw not in (None, "", [], {}):
            source_fields.append({"field": field, "source": source, "value": normalized if normalized is not None else raw})

    def normalize_margin(value: Any) -> float | None:
        margin = _to_number(value)
        if margin is not None and margin <= 1:
            margin = round(margin * 100, 4)
        return margin

    profile_shares = _to_number(_first(profile.get("shares"), profile.get("holding_units")))
    holding_shares = _to_number(_first(holding.get("shares"), holding.get("holding_units")))
    profile_cost = _to_number(_first(profile.get("cost_price"), profile.get("cost")))
    holding_cost = _to_number(_first(holding.get("cost_price"), holding.get("cost")))
    profile_margin = normalize_margin(_first(profile.get("margin_ratio_pct"), profile.get("margin_ratio")))
    holding_margin = normalize_margin(_first(holding.get("margin_ratio_pct"), holding.get("margin_ratio")))
    profile_current = _to_number(profile.get("current_price"))
    holding_current = _to_number(holding.get("current_price"))
    latest_price = _to_number(latest_close)

    add_source("shares", "position_profile.shares", profile.get("shares") or profile.get("holding_units"), profile_shares)
    add_source("shares", "home_snapshot.holding_action.shares", holding.get("shares") or holding.get("holding_units"), holding_shares)
    add_source("cost_price", "position_profile.cost_price", profile.get("cost_price") or profile.get("cost"), profile_cost)
    add_source("cost_price", "home_snapshot.holding_action.cost_price", holding.get("cost_price") or holding.get("cost"), holding_cost)
    add_source("financing_ratio", "position_profile.margin_ratio_pct", _first(profile.get("margin_ratio_pct"), profile.get("margin_ratio")), profile_margin)
    add_source("financing_ratio", "home_snapshot.holding_action.margin_ratio", _first(holding.get("margin_ratio_pct"), holding.get("margin_ratio")), holding_margin)
    add_source("current_price", "command_center_daily_close_packet.latest_close", latest_close, latest_price)
    add_source("current_price", "home_snapshot.holding_action.current_price", holding.get("current_price"), holding_current)
    add_source("current_price", "position_profile.current_price", profile.get("current_price"), profile_current)

    def conflict(field: str, first_value: float | None, second_value: float | None, tolerance: float = 0.0001) -> bool:
        if first_value is None or second_value is None:
            return False
        return abs(first_value - second_value) > tolerance

    conflict_flags = []
    if conflict("shares", profile_shares, holding_shares):
        conflict_flags.append("shares_conflict")
    if conflict("cost_price", profile_cost, holding_cost):
        conflict_flags.append("cost_price_conflict")
    if conflict("financing_ratio", profile_margin, holding_margin):
        conflict_flags.append("financing_ratio_conflict")
    if conflict("current_price", latest_price, holding_current, tolerance=0.01):
        conflict_flags.append("current_price_conflict")

    current_price = _to_number(_first(latest_price, holding_current, profile_current))
    cost_price = _to_number(_first(profile_cost, holding_cost))
    shares = _to_number(_first(profile_shares, holding_shares))
    margin_ratio = _to_number(_first(profile_margin, holding_margin))
    if margin_ratio is not None and margin_ratio <= 1:
        margin_ratio = round(margin_ratio * 100, 4)
    floating_pnl_pct = _to_number(_first(holding.get("floating_pnl_pct"), _as_mapping(holding.get("floating_pnl")).get("pct"), profile.get("pnl_pct")))
    floating_pnl_amount = _to_number(_first(holding.get("floating_pnl_amount"), _as_mapping(holding.get("floating_pnl")).get("amount"), profile.get("pnl_amount")))
    if current_price is not None and cost_price not in (None, 0) and shares:
        floating_pnl_pct = floating_pnl_pct if floating_pnl_pct is not None else round((current_price / cost_price - 1) * 100, 4)
        floating_pnl_amount = floating_pnl_amount if floating_pnl_amount is not None else round((current_price - cost_price) * shares, 2)
    market_value = round(current_price * shares, 2) if current_price is not None and shares is not None else None
    source_priority = "position_profile > home_snapshot.holding_action > command_center_daily_close_packet"
    source_packets = []
    if profile:
        source_packets.append("position_profile")
    if latest_price is not None:
        source_packets.append("command_center_daily_close_packet")
    if holding:
        source_packets.append("home_snapshot.holding_action")
    return {
        "current_price": current_price,
        "cost_price": cost_price,
        "shares": shares,
        "market_value": market_value,
        "floating_pnl_pct": floating_pnl_pct,
        "floating_pnl_amount": floating_pnl_amount,
        "financing_ratio": margin_ratio,
        "ticker": _display_a_share_ticker(_first(target, holding.get("ticker"), profile.get("ticker"))),
        "name": _to_text(_first(name, holding.get("name"), profile.get("name"))),
        "source_packet": "+".join(dict.fromkeys(source_packets)) or "unknown",
        "source_fields": source_fields,
        "source_priority": source_priority,
        "local_updated_at": _to_text(_first(profile.get("updated_at"), holding.get("updated_at"), snapshot.get("updated_at"), snapshot.get("timestamp"))),
        "is_user_verified_position": bool(profile_shares is not None or profile_cost is not None or holding_shares is not None or holding_cost is not None),
        "conflict_flags": list(dict.fromkeys(conflict_flags)),
    }


def _quant_context(strategy_packet: Any = None, decision_packet: Any = None, home_snapshot: Any = None) -> dict:
    strategy = _as_mapping(strategy_packet)
    decision = _as_mapping(decision_packet)
    snapshot = _as_mapping(home_snapshot)
    quant = _as_mapping(snapshot.get("quant_packet"))
    discipline = _as_mapping(snapshot.get("discipline_packet"))
    risk_budget = _as_mapping(strategy.get("risk_budget") or snapshot.get("position_risk_budget"))
    win_rate = _to_number(_first(strategy.get("win_rate"), discipline.get("win_rate"), quant.get("win_rate")))
    expected_return = _to_number(_first(strategy.get("expected_return"), quant.get("expected_return"), quant.get("return_pct")))
    max_drawdown = _to_number(_first(strategy.get("max_drawdown"), discipline.get("max_drawdown"), quant.get("max_drawdown")))
    risk_reward = _to_number(_first(strategy.get("risk_reward"), quant.get("risk_reward"), discipline.get("risk_reward")))
    return {
        "backtest_signal": _to_text(_first(strategy.get("latest_signal"), discipline.get("latest_signal"), discipline.get("signal")), "待验证"),
        "win_rate": win_rate,
        "expected_return": expected_return,
        "max_drawdown": max_drawdown,
        "risk_reward": risk_reward,
        "suggested_action": _to_text(_first(strategy.get("action"), strategy.get("overall_action"), decision.get("overall_action")), "等待"),
        "discipline_constraints": [
            text
            for text in [
                _to_text(strategy.get("add_condition")),
                _to_text(strategy.get("reduce_condition")),
                _to_text(strategy.get("invalidation_condition")),
            ]
            if text
        ],
        "risk_budget": risk_budget,
        "source": "strategy_execution_packet + discipline/quant cache",
    }


def _trade_lab_context(records: Any = None) -> dict:
    items = [item for item in _as_list(records) if isinstance(item, Mapping)]
    behavior_bias = []
    discipline_notes = []
    position_notes = []
    for item in items[:8]:
        text = " ".join(
            [
                _to_text(item.get("user_note")),
                " ".join(_to_text(value) for value in _as_list(item.get("validation_conditions"))),
                _to_text(item.get("overall_action")),
                _to_text(item.get("strategy_action")),
            ]
        )
        if "追高" in text:
            behavior_bias.append("追高风险")
            discipline_notes.append("近期复盘出现追高相关记录，禁止因为单日强势额外加杠杆。")
        if "过早止盈" in text:
            behavior_bias.append("过早止盈")
        if "扛亏" in text or "浮亏" in text:
            behavior_bias.append("扛亏风险")
        if "频繁" in text:
            behavior_bias.append("频繁交易")
        if item.get("position_budget"):
            position_notes.append("复盘记录包含仓位/风险预算，可作为本轮纪律提醒。")
    return {
        "recent_review_flags": [_to_text(item.get("user_decision"), "未执行") for item in items[:5]],
        "behavior_bias": list(dict.fromkeys(behavior_bias)),
        "discipline_notes": list(dict.fromkeys(discipline_notes))[:5],
        "position_management_notes": list(dict.fromkeys(position_notes))[:5],
        "record_count": len(items),
    }


def _weight_model(action: str, items: list[dict], position: dict, rows: list[dict]) -> tuple[dict, list[str]]:
    action_text = _to_text(action)
    if any(word in action_text for word in ("降风险", "减仓", "止损")):
        weights = {"bullish": 0.12, "neutral": 0.34, "cautious": 0.54}
    elif any(word in action_text for word in ("进攻", "加仓", "试探")):
        weights = {"bullish": 0.34, "neutral": 0.46, "cautious": 0.20}
    elif "只观察" in action_text:
        weights = {"bullish": 0.18, "neutral": 0.56, "cautious": 0.26}
    else:
        weights = {"bullish": 0.25, "neutral": 0.50, "cautious": 0.25}
    notes = []
    verified = sum(1 for item in items if item.get("status") == "verified")
    blockers = sum(1 for item in items if item.get("status") in BLOCKING_STATUSES)
    if verified >= 4:
        weights["bullish"] += 0.04
        weights["neutral"] -= 0.02
        weights["cautious"] -= 0.02
        notes.append("A股事实验证较充分，路径权重略向可执行情景倾斜。")
    if blockers >= 3:
        weights["bullish"] -= 0.05
        weights["cautious"] += 0.05
        notes.append("多项 A股事实仍缺失/阻断，压低乐观路径权重。")
    margin = _to_number(position.get("financing_ratio"), 0) or 0
    if margin >= 20:
        weights["bullish"] -= 0.05
        weights["cautious"] += 0.05
        notes.append("融资比例较高，谨慎路径权重上调。")
    if not rows:
        notes.append("缺少真实日线，价格区间只保留操作纪律，不画真实历史段。")
    total = sum(max(value, 0.05) for value in weights.values())
    return {key: round(max(value, 0.05) / total, 4) for key, value in weights.items()}, notes


def _price_zone(anchor: float | None, technical: Mapping[str, Any], scenario: str) -> dict:
    atr = _to_number(technical.get("atr"))
    vol_pct = _to_number(technical.get("volatility_20d"), 2.0) or 2.0
    if anchor is None:
        return {"next_session_low": None, "next_session_high": None, "five_to_ten_day_zone": []}
    step = atr if atr and atr > 0 else anchor * max(vol_pct / 100, 0.015)
    if scenario == "bullish":
        low, high = anchor + step * 0.15, anchor + step * 1.35
        zone = [round(anchor + step * 0.6, 4), round(anchor + step * 2.4, 4)]
    elif scenario == "cautious":
        low, high = anchor - step * 1.45, anchor - step * 0.15
        zone = [round(anchor - step * 2.6, 4), round(anchor - step * 0.7, 4)]
    else:
        low, high = anchor - step * 0.65, anchor + step * 0.65
        zone = [round(anchor - step * 1.1, 4), round(anchor + step * 1.1, 4)]
    return {
        "next_session_low": round(low, 4),
        "next_session_high": round(high, 4),
        "five_to_ten_day_zone": zone,
    }


def _scenario_chart_points(anchor: float | None, zone: Mapping[str, Any], scenario: str) -> list[dict]:
    return [
        {"x": "T0", "price": anchor, "source": "latest_real_close_or_current_price"},
        {"x": "T+1_open", "price": zone.get("next_session_low") if scenario == "cautious" else anchor, "source": "model_scenario"},
        {"x": "T+1_close", "price": zone.get("next_session_high") if scenario == "bullish" else zone.get("next_session_low") if scenario == "cautious" else anchor, "source": "model_scenario"},
        {"x": "T+5", "price": (zone.get("five_to_ten_day_zone") or [None, None])[-1 if scenario == "bullish" else 0], "source": "model_scenario"},
        {"x": "T+10", "price": (zone.get("five_to_ten_day_zone") or [None, None])[-1 if scenario != "cautious" else 0], "source": "model_scenario"},
    ]


def _scenario_paths(
    *,
    position: dict,
    technical: dict,
    quant: dict,
    fact_items: list[dict],
    trade_lab: dict,
    rows: list[dict],
) -> list[dict]:
    position_conflicts = list(position.get("conflict_flags") or [])
    anchor = _to_number(position.get("current_price")) or _to_number(_as_mapping(_daily_lineage(rows, {})).get("latest_close"))
    weights, weight_notes = _weight_model(_to_text(quant.get("suggested_action")), fact_items, position, rows)
    verified_names = [
        _to_text(item.get("fact_name"))
        for item in fact_items
        if item.get("status") == "verified" and item.get("enters_projection", True)
    ]
    blocked_names = [
        _to_text(item.get("fact_name"))
        for item in fact_items
        if item.get("status") in BLOCKING_STATUSES
    ]
    common_evidence = verified_names[:4] or ["真实日线", "策略执行结果", "交易纪律"]
    no_chase = any("追高" in _to_text(note) for note in trade_lab.get("behavior_bias") or []) or (_to_number(position.get("financing_ratio"), 0) or 0) >= 20
    bullish_zone = _price_zone(anchor, technical, "bullish")
    neutral_zone = _price_zone(anchor, technical, "neutral")
    cautious_zone = _price_zone(anchor, technical, "cautious")
    action = _to_text(quant.get("suggested_action"), "等待")
    paths = [
        {
            "scenario_key": "bullish",
            "scenario_name": "乐观路径",
            "weight": weights["bullish"],
            "weight_label": "情景权重" + ("（fallback_weight）" if not rows or len(verified_names) < 2 else ""),
            "path_source": "quant_rule_deterministic_base",
            "trigger_conditions": [
                "价格站稳压力位或 MA20 上方，且量能/资金事实不再阻断。",
                "策略执行仍保持等待/只观察以上，不出现降风险。",
            ],
            "invalid_conditions": [
                "跌破成本线或关键支撑后，本路径失效。",
                *([f"待验证事实未恢复：{'、'.join(blocked_names[:3])}"] if blocked_names else []),
            ],
            "expected_price_zone": bullish_zone,
            "chart_points": _scenario_chart_points(anchor, bullish_zone, "bullish"),
            "operation_plan": {
                "primary_action": "wait" if no_chase else "hold",
                "position_change": "none" if no_chase else "add_small",
                "execution_rules": [
                    "不追高；只在触发条件满足后考虑小幅试探。",
                    "融资比例较高时只允许用已有现金观察，不额外加杠杆。",
                ],
                "risk_controls": ["若冲高无量或数据缺口扩大，回到中性路径。"],
            },
            "evidence_used": common_evidence,
            "confidence_note": "乐观路径仅代表可准备情景，不是买入信号。" + ("；".join(weight_notes[:2]) if weight_notes else ""),
        },
        {
            "scenario_key": "neutral",
            "scenario_name": "中性路径",
            "weight": weights["neutral"],
            "weight_label": "情景权重" + ("（fallback_weight）" if not rows or len(verified_names) < 2 else ""),
            "path_source": "quant_rule_deterministic_base",
            "trigger_conditions": ["价格在成本线/支撑压力之间震荡，事实链路没有新增强证据。"],
            "invalid_conditions": ["放量突破转入乐观路径；跌破支撑转入谨慎路径。"],
            "expected_price_zone": neutral_zone,
            "chart_points": _scenario_chart_points(anchor, neutral_zone, "neutral"),
            "operation_plan": {
                "primary_action": "wait" if action in {"等待", "只观察"} else "hold",
                "position_change": "none",
                "execution_rules": ["持仓观察，等待明日验证条件。"],
                "risk_controls": ["不因单日波动改变核心仓位。"],
            },
            "evidence_used": common_evidence,
            "confidence_note": "中性路径是默认操作基准；不自动改写策略 action。",
        },
        {
            "scenario_key": "cautious",
            "scenario_name": "谨慎路径",
            "weight": weights["cautious"],
            "weight_label": "情景权重" + ("（fallback_weight）" if not rows or len(verified_names) < 2 else ""),
            "path_source": "quant_rule_deterministic_base",
            "trigger_conditions": ["跌破支撑/成本线，或公告硬风险、融资风险、资金流继续恶化。"],
            "invalid_conditions": ["重新站回支撑位且风险事实恢复后，谨慎路径降级。"],
            "expected_price_zone": cautious_zone,
            "chart_points": _scenario_chart_points(anchor, cautious_zone, "cautious"),
            "operation_plan": {
                "primary_action": "reduce" if _to_number(position.get("shares"), 0) else "no_action",
                "position_change": "reduce_10_20_pct" if _to_number(position.get("shares"), 0) else "none",
                "execution_rules": ["先降风险、再复盘，不做摊薄式补仓。"],
                "risk_controls": ["若融资比例存在压力，优先降低杠杆暴露。"],
            },
            "evidence_used": list(dict.fromkeys([*common_evidence, *blocked_names[:3]])),
            "confidence_note": "谨慎路径用于风控预案；数据缺口越多，越不能忽视该路径。",
        },
    ]
    if position_conflicts:
        conflict_text = "持仓来源冲突：" + "、".join(position_conflicts)
        for path in paths:
            plan = dict(_as_mapping(path.get("operation_plan")))
            plan["primary_action"] = "verify"
            plan["position_change"] = "none"
            plan["execution_rules"] = [
                "先核验持仓数量、成本价和融资比例；冲突解除前不生成强操作建议。",
                "只允许观察、复核和写复盘记录，不自动加仓、减仓或追高。",
            ]
            plan["risk_controls"] = list(dict.fromkeys([*(_as_list(plan.get("risk_controls"))), "持仓来源冲突未解除前，所有路径降级为观察。"]))
            path["operation_plan"] = plan
            path["confidence_note"] = f"{path.get('confidence_note') or ''}；{conflict_text}"
            path.setdefault("invalid_conditions", []).append("持仓来源冲突未解除，本路径不可执行。")
    return paths


def _operation_zones(position: dict, technical: dict, trade_lab: dict) -> list[dict]:
    current = _to_number(position.get("current_price"))
    cost = _to_number(position.get("cost_price"))
    supports = [_to_number(item) for item in _as_list(technical.get("support_levels"))]
    supports = [item for item in supports if item is not None]
    resistances = [_to_number(item) for item in _as_list(technical.get("resistance_levels"))]
    resistances = [item for item in resistances if item is not None]
    support = max([value for value in supports if current is None or value <= current], default=(cost or current))
    resistance = min([value for value in resistances if current is None or value >= current], default=(current or cost))
    atr = _to_number(technical.get("atr")) or ((current or cost or 100) * 0.02)
    return [
        {
            "zone_key": "profit_take_zone",
            "zone_name": "止盈/减仓观察区",
            "price_range": [round((resistance or current or 0), 4) if resistance else None, round((resistance or current or 0) + atr, 4) if resistance or current else None],
            "action": "reduce_or_take_profit",
            "condition": "冲高进入压力区域但量能/事实未继续确认时，先观察止盈或分批减仓。",
            "source": "technical_context + strategy_execution_packet",
        },
        {
            "zone_key": "do_not_chase_zone",
            "zone_name": "禁止追高区",
            "price_range": [round((resistance or current or 0) + atr, 4) if resistance or current else None, round((resistance or current or 0) + atr * 2, 4) if resistance or current else None],
            "action": "do_not_chase",
            "condition": "未放量验证、融资比例偏高或复盘有追高风险时，不追涨加仓。",
            "source": "trade_lab_discipline",
        },
        {
            "zone_key": "pullback_watch_zone",
            "zone_name": "回踩观察区",
            "price_range": [round((support or current or 0), 4) if support or current else None, round((current or support or 0), 4) if current or support else None],
            "action": "watch_or_condition_add",
            "condition": "回踩不破支撑且事实链路恢复后，才允许按风险预算小幅观察。",
            "source": "technical_context + quant_context",
        },
        {
            "zone_key": "risk_break_zone",
            "zone_name": "破位风控区",
            "price_range": [round((support or cost or 0) - atr * 2, 4) if support or cost else None, round((support or cost or 0), 4) if support or cost else None],
            "action": "risk_control_or_stop_loss",
            "condition": "跌破支撑/成本纪律线或融资压力放大，优先降风险。",
            "source": "strategy_execution_packet",
        },
        {
            "zone_key": "review_zone",
            "zone_name": "强制复盘区",
            "price_range": [None, None],
            "action": "review",
            "condition": "与本轮路径明显偏离，或交易记录提示纪律偏差时，先写复盘记录。",
            "source": "trade_review_log",
        },
    ]


def _chart_render_model(rows: list[dict], scenarios: list[dict], position: dict, technical: dict, zones: list[dict]) -> dict:
    historical = [
        {
            "x": item.get("trade_date") or f"H{index}",
            "price": item.get("close"),
            "source": "tushare.daily.close",
            "vol": item.get("vol"),
            "amount": item.get("amount"),
        }
        for index, item in enumerate(rows)
    ]
    return {
        "historical_series": historical,
        "scenario_series": [
            {
                "scenario_key": scenario.get("scenario_key"),
                "scenario_name": scenario.get("scenario_name"),
                "points": scenario.get("chart_points") or [],
            }
            for scenario in scenarios
        ],
        "cost_line": position.get("cost_price"),
        "current_price_line": position.get("current_price"),
        "support_lines": technical.get("support_levels") or [],
        "resistance_lines": technical.get("resistance_levels") or [],
        "operation_zone_overlays": zones,
        "annotations": [
            {
                "text": "图谱用于可视化 next action 和条件路径，不自动改写交易指令。",
                "source": "guardrail",
            }
        ],
    }


def _data_trust_summary(
    *,
    daily_lineage: Mapping[str, Any],
    fact_call_ledger_items: list[dict],
    position: Mapping[str, Any],
    deepseek_status: str = "not_called",
) -> dict:
    facts = [
        {
            "fact_key": item.get("fact_key"),
            "fact_name": item.get("fact_name"),
            "scope": item.get("scope"),
            "call_status": item.get("call_status"),
            "call_status_label": item.get("call_status_label"),
            "lineage_status": item.get("lineage_status"),
            "row_count": item.get("row_count"),
            "target_match_count": item.get("target_match_count"),
            "market_row_count": item.get("market_row_count"),
            "data_date": item.get("data_date"),
            "note": item.get("error_message_safe") or ("成功无记录" if item.get("call_status") == "verified_no_record" else ""),
            "scope_note": item.get("scope_note") or "",
            "scope_breakdown": item.get("scope_breakdown") or [],
            "is_target_stock_evidence": item.get("is_target_stock_evidence"),
            "is_market_context_evidence": item.get("is_market_context_evidence"),
            "is_industry_or_concept_evidence": item.get("is_industry_or_concept_evidence"),
        }
        for item in fact_call_ledger_items
    ]
    return {
        "schema_version": "next_session_data_trust_summary.v1",
        "daily_close": {
            "label": "真实日线",
            "call_status": "verified_present" if daily_lineage.get("is_real_market_series") else "missing_packet",
            "row_count": daily_lineage.get("row_count") or 0,
            "date_range": [daily_lineage.get("start_date"), daily_lineage.get("end_date")],
            "latest_close": daily_lineage.get("latest_close"),
        },
        "position": {
            "label": "持仓",
            "call_status": "conflict" if position.get("conflict_flags") else "verified" if position.get("is_user_verified_position") else "not_called",
            "conflict_flags": position.get("conflict_flags") or [],
            "source_packet": position.get("source_packet"),
        },
        "facts": facts,
        "deepseek": {"label": "DeepSeek", "status": deepseek_status},
        "primary_dependency": [
            item.get("fact_name")
            for item in facts
            if item.get("call_status") in {"verified_present", "verified_no_record"}
        ],
    }


def build_next_session_operation_projection_packet(
    *,
    target: Any = "",
    name: Any = "",
    trade_date: Any = "",
    daily_close_packet: Any = None,
    home_snapshot: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    a_share_fact_lineage_summary: Any = None,
    a_share_fact_call_ledger: Any = None,
    position_profile: Any = None,
    recent_trade_reviews: Any = None,
    now: Any = None,
) -> dict:
    rows, daily_source = _daily_rows_from_sources(
        daily_close_packet=daily_close_packet,
        home_snapshot=home_snapshot,
        live_packet=live_packet,
    )
    daily_lineage = _daily_lineage(rows, daily_source, now=now)
    fact_lineage = _as_mapping(a_share_fact_lineage_summary) or _as_mapping(_as_mapping(home_snapshot).get("a_share_fact_lineage_summary"))
    fact_call_items = _fact_call_ledger_items(
        a_share_fact_call_ledger
        or _as_mapping(home_snapshot).get("a_share_fact_call_ledger")
        or _as_mapping(live_packet).get("a_share_fact_call_ledger"),
        daily_close_packet=daily_source,
    )
    fact_items = _lineage_items(fact_lineage, fact_call_items)
    position = _position_context(
        target=target,
        name=name,
        position_profile=position_profile,
        home_snapshot=home_snapshot,
        latest_close=daily_lineage.get("latest_close"),
    )
    technical = _technical_context(rows, fact_items)
    quant = _quant_context(strategy_packet=strategy_packet, decision_packet=decision_packet, home_snapshot=home_snapshot)
    trade_lab = _trade_lab_context(recent_trade_reviews)
    scenarios = _scenario_paths(
        position=position,
        technical=technical,
        quant=quant,
        fact_items=fact_items,
        trade_lab=trade_lab,
        rows=rows,
    )
    zones = _operation_zones(position, technical, trade_lab)
    updated_at = _now_iso(now)
    warning_list = [
        "该图谱是操作推演，不是确定性价格预测。",
        "DeepSeek 只基于输入数据整理路径，不验证输入之外的事实。",
    ]
    if not rows:
        warning_list.insert(0, "真实日线缺失，无法生成真实历史段。")
    data_trust_summary = _data_trust_summary(
        daily_lineage=daily_lineage,
        fact_call_ledger_items=fact_call_items,
        position=position,
        deepseek_status="not_called",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if rows else "missing_daily_close",
        "updated_at": updated_at,
        "ts_code": _display_a_share_ticker(target),
        "trade_date": _date_text(trade_date) or daily_lineage.get("end_date"),
        "projection_horizon": {"primary": "next_session", "extended": "5_to_10_trading_days"},
        "data_lineage": {
            "daily_close": daily_lineage,
            "a_share_fact_lineage_summary": {
                **fact_lineage,
                "items": fact_items,
            },
            "a_share_fact_call_ledger": {
                "schema_version": "a_share_fact_call_ledger.v1",
                "updated_at": updated_at,
                "items": fact_call_items,
            },
            "quant_packet": {"source": "strategy_execution_packet + command_center_quant_packet", "status": _to_text(quant.get("suggested_action"), "等待")},
            "trade_lab_packet": {"source": "trade_review_log", "record_count": trade_lab.get("record_count")},
            "strategy_execution_packet": {"action": quant.get("suggested_action"), "does_not_modify_action": True},
        },
        "position_context": position,
        "technical_context": technical,
        "quant_context": quant,
        "trade_lab_context": trade_lab,
        "scenario_paths": scenarios,
        "operation_zones": zones,
        "chart_render_model": _chart_render_model(rows, scenarios, position, technical, zones),
        "data_trust_summary": data_trust_summary,
        "deepseek_synthesis": {
            "enabled": True,
            "called_at": None,
            "model": None,
            "input_hash": None,
            "status": "not_called",
            "summary": "",
            "raw_json": None,
        },
        "warnings": warning_list,
        "guardrail": "图谱用于可视化 next action 和条件路径，不自动改写交易指令。",
        "deepseek_called": False,
        "external_call_policy": "uses_cached_or_manual_tushare_only",
    }


def build_next_session_deepseek_prompt(packet: Any, *, retry_mode: bool = False) -> dict:
    payload = _as_mapping(packet)
    data_lineage = _as_mapping(payload.get("data_lineage"))
    daily_close = _as_mapping(data_lineage.get("daily_close"))
    position_context = payload.get("position_context") or {}
    quant_context = payload.get("quant_context") or {}
    trade_lab_context = payload.get("trade_lab_context") or {}
    fact_lineage = _as_mapping(data_lineage.get("a_share_fact_lineage_summary"))
    fact_call_ledger = _as_mapping(data_lineage.get("a_share_fact_call_ledger"))
    compact_input = {
        "schema_version": SCHEMA_VERSION,
        "ts_code": payload.get("ts_code"),
        "trade_date": payload.get("trade_date"),
        "position_context": position_context,
        "daily_close": daily_close,
        "technical_context": payload.get("technical_context") or {},
        "quant_context": quant_context,
        "trade_lab_context": trade_lab_context,
        "a_share_fact_lineage_summary": fact_lineage,
        "a_share_fact_call_ledger": fact_call_ledger,
        "data_trust_summary": payload.get("data_trust_summary") or {},
        "deterministic_projection_base": {
            "scenario_paths": payload.get("scenario_paths") or [],
            "operation_zones": payload.get("operation_zones") or [],
            "warnings": payload.get("warnings") or [],
        },
    }
    input_hash = _safe_hash(compact_input)
    component_hashes = {
        "position_hash": _safe_hash(position_context),
        "quant_context_hash": _safe_hash(quant_context),
        "a_share_fact_lineage_hash": _safe_hash(fact_lineage),
        "a_share_fact_call_ledger_hash": _safe_hash(fact_call_ledger),
        "trade_lab_context_hash": _safe_hash(trade_lab_context),
    }
    cache_key = "|".join(
        [
            PACKET_KEY,
            _to_text(payload.get("ts_code"), "unknown"),
            _to_text(payload.get("trade_date"), "unknown"),
            _to_text(daily_close.get("latest_close"), "no_close"),
            component_hashes["position_hash"],
            component_hashes["quant_context_hash"],
            component_hashes["a_share_fact_lineage_hash"],
            component_hashes["a_share_fact_call_ledger_hash"],
            component_hashes["trade_lab_context_hash"],
        ]
    )
    system_prompt = (
        "你是 A 股交易操作图谱 JSON 整理器。你不联网，不验证输入外事实。"
        "你只能基于用户提供的 JSON 数据，整理情景路径、触发条件和操作纪律。"
        "输出不是确定性价格预测。不得把缺失、待验证、阻断、权限不足、成功无记录的数据当作已验证利好。"
        "你的全部回答必须是一个合法 JSON object。禁止 markdown，禁止代码块围栏，禁止解释文字。"
        "顶层键只允许 summary、scenario_paths、operation_zones、annotations、warnings。"
        "不得输出或覆盖 ts_code、trade_date、position_context、daily_close、latest_close、row_count、source_interface、strategy_execution_packet、quant_context。"
    )
    retry_clause = (
        "这是 JSON 重试请求。请更短、更严格：只输出合法 JSON object，顶层键只允许 summary、scenario_paths、operation_zones、annotations、warnings。"
        if retry_mode
        else ""
    )
    user_prompt = (
        f"{retry_clause}"
        "请基于以下 JSON 输出 next_session_operation_projection.v1 的可合并 JSON。"
        "必须至少包含 scenario_paths 或 operation_zones 之一。"
        "不要添加输入之外的事实。不要输出 markdown。不要输出 ```json。只输出 JSON。"
        "数字价位必须说明来源：真实 close、成本、ATR、支撑压力、量化规则或 DeepSeek 整理。\n\n"
        + json.dumps(compact_input, ensure_ascii=False, sort_keys=True, default=str)
    )
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "input_hash": input_hash,
        "cache_key": cache_key,
        "component_hashes": component_hashes,
        "deepseek_called": False,
        "required_json_only": True,
        "retry_mode": bool(retry_mode),
        "allowed_top_level_keys": sorted(DEEPSEEK_MERGE_ALLOWED_KEYS),
    }


def _extract_json_object_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    start = raw.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start:index + 1]
    return ""


def extract_deepseek_projection_json(deepseek_payload: Any) -> tuple[dict, str]:
    if isinstance(deepseek_payload, Mapping):
        return dict(deepseek_payload), ""
    if not isinstance(deepseek_payload, str):
        return {}, "DeepSeek 返回类型不是 JSON object。"
    text = _extract_json_object_text(deepseek_payload)
    if not text:
        return {}, "DeepSeek 返回中未找到 JSON object。"
    try:
        parsed = json.loads(text)
    except Exception as exc:
        return {}, f"DeepSeek JSON 解析失败：{exc}"
    if not isinstance(parsed, dict):
        return {}, "DeepSeek JSON 顶层不是 object。"
    return parsed, ""


def _sanitize_deepseek_projection_payload(parsed: Mapping[str, Any]) -> tuple[dict, list[str], list[str]]:
    payload = dict(parsed or {})
    ignored_keys = sorted(set(payload.keys()) - DEEPSEEK_MERGE_ALLOWED_KEYS)
    blocked_immutable_keys = sorted(set(payload.keys()) & DEEPSEEK_MERGE_IMMUTABLE_KEYS)
    sanitized = {key: payload[key] for key in DEEPSEEK_MERGE_ALLOWED_KEYS if key in payload}
    if "scenario_paths" in sanitized and not isinstance(sanitized.get("scenario_paths"), list):
        ignored_keys.append("scenario_paths")
        sanitized.pop("scenario_paths", None)
    if "operation_zones" in sanitized and not isinstance(sanitized.get("operation_zones"), list):
        ignored_keys.append("operation_zones")
        sanitized.pop("operation_zones", None)
    if "annotations" in sanitized and not isinstance(sanitized.get("annotations"), list):
        ignored_keys.append("annotations")
        sanitized.pop("annotations", None)
    if "warnings" in sanitized and not isinstance(sanitized.get("warnings"), list):
        ignored_keys.append("warnings")
        sanitized.pop("warnings", None)
    if "summary" in sanitized:
        sanitized["summary"] = _to_text(sanitized.get("summary"))
    return sanitized, sorted(set(ignored_keys)), blocked_immutable_keys


def merge_deepseek_next_session_projection(
    packet: Any,
    deepseek_payload: Any,
    *,
    called_at: Any = None,
    model: Any = "deepseek-chat",
    input_hash: Any = "",
) -> dict:
    base = dict(_as_mapping(packet))
    parsed, parse_error = extract_deepseek_projection_json(deepseek_payload)
    synthesis = dict(_as_mapping(base.get("deepseek_synthesis")))
    raw_output_hash = _safe_hash(deepseek_payload) if deepseek_payload not in (None, "") else ""
    sanitized, ignored_keys, blocked_immutable_keys = _sanitize_deepseek_projection_payload(parsed)
    has_required = any(key in sanitized for key in DEEPSEEK_REQUIRED_STRUCTURED_KEYS)
    if not parsed or parse_error or not has_required:
        synthesis.update(
            {
                "status": "parse_failed",
                "called_at": _now_iso(called_at),
                "model": _to_text(model),
                "input_hash": _to_text(input_hash),
                "summary": "DeepSeek 未返回可合并 JSON；保留本地确定性图谱。",
                "raw_json": None,
                "raw_output_hash": raw_output_hash,
                "error_message_safe": parse_error or "DeepSeek JSON 缺少 scenario_paths 或 operation_zones。",
                "allowed_merge_keys": sorted(DEEPSEEK_MERGE_ALLOWED_KEYS),
                "ignored_top_level_keys": ignored_keys,
                "blocked_immutable_keys": blocked_immutable_keys,
            }
        )
        base["deepseek_synthesis"] = synthesis
        if isinstance(base.get("data_trust_summary"), Mapping):
            trust = dict(base.get("data_trust_summary") or {})
            trust["deepseek"] = {"label": "DeepSeek", "status": "parse_failed"}
            base["data_trust_summary"] = trust
        base["deepseek_called"] = True
        return base
    if isinstance(sanitized.get("scenario_paths"), list):
        base["scenario_paths"] = sanitized["scenario_paths"]
        chart = dict(_as_mapping(base.get("chart_render_model")))
        chart["scenario_series"] = [
            {
                "scenario_key": item.get("scenario_key"),
                "scenario_name": item.get("scenario_name"),
                "points": item.get("chart_points") or [],
            }
            for item in sanitized["scenario_paths"]
            if isinstance(item, Mapping)
        ]
        base["chart_render_model"] = chart
    if isinstance(sanitized.get("operation_zones"), list):
        base["operation_zones"] = sanitized["operation_zones"]
        chart = dict(_as_mapping(base.get("chart_render_model")))
        chart["operation_zone_overlays"] = sanitized["operation_zones"]
        base["chart_render_model"] = chart
    annotations = sanitized.get("annotations") if isinstance(sanitized.get("annotations"), list) else []
    if annotations:
        chart = dict(_as_mapping(base.get("chart_render_model")))
        chart["annotations"] = annotations
        base["chart_render_model"] = chart
    warnings = sanitized.get("warnings") if isinstance(sanitized.get("warnings"), list) else []
    if warnings:
        base["warnings"] = list(dict.fromkeys([*_as_list(base.get("warnings")), *warnings]))
    synthesis.update(
        {
            "status": "success",
            "called_at": _now_iso(called_at),
            "model": _to_text(model),
            "input_hash": _to_text(input_hash),
            "output_hash": _safe_hash(sanitized),
            "raw_output_hash": raw_output_hash,
            "summary": _to_text(sanitized.get("summary"), "DeepSeek 已整理路径，但不验证输入外事实。"),
            "raw_json": sanitized,
            "error_message_safe": None,
            "allowed_merge_keys": sorted(DEEPSEEK_MERGE_ALLOWED_KEYS),
            "ignored_top_level_keys": ignored_keys,
            "blocked_immutable_keys": blocked_immutable_keys,
        }
    )
    base["deepseek_synthesis"] = synthesis
    if isinstance(base.get("data_trust_summary"), Mapping):
        trust = dict(base.get("data_trust_summary") or {})
        trust["deepseek"] = {"label": "DeepSeek", "status": "success"}
        base["data_trust_summary"] = trust
    base["deepseek_called"] = True
    base["updated_at"] = _now_iso(called_at)
    return base


def next_session_projection_ui_copy() -> dict:
    return {
        "title": "次日操作图谱：真实日线 + 量化推演 + 交易纪律 + DeepSeek 整理",
        "not_called": "当前为本地量化规则图谱，可手动调用 DeepSeek 整理路径说明",
        "called": "DeepSeek 已整理路径，但不验证输入外事实",
        "guardrail": "图谱用于可视化 next action 和条件路径，不自动改写交易指令。",
        "prediction_boundary": "非确定性预测",
    }
